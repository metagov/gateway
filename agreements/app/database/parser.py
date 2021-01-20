from tinydb.database import Document
from tinydb import where
import re
import requests

class Parser:
    def __init__(self, db):
        self.db = db
        self.tweets = db.table('tweets')
        self.threads = db.table('threads')

        if not self.threads.contains(doc_id=0):
            self.threads.insert(Document(
                {
                    'num_threads': 0
                },
                doc_id=0))
        
    def add(self, status):
        # ensures tweet hasn't been added before
        if self.tweets.contains(doc_id=status.id):
            print(f'Status #{status.id} already in database')
            return

        parent_id = status.in_reply_to_status_id
        if parent_id:
            parent_id = str(parent_id)

        # recording data to store in database
        tweet = {
            'text': status.full_text,                    # text of the tweet
            'user_full_name': status.user.name,          # actual name of poster
            'user_screen_name': status.user.screen_name, # user name of poster
            'user_id': str(status.user.id),                   # user id of poster
            'created': str(status.created_at),           # date and time created
            'parent_id': parent_id,   # id of tweet replying
            'child_ids': [],
            'parsed': False,                             # whether tweet has been parsed
            'thread_id': 0                               # corresponding id in threads table
        }

        # inserts data into database under the tweet's id
        self.tweets.insert(
            Document(
                tweet, 
                doc_id=status.id
            )
        )
    
    # recursive function to find the root message of a reply
    def find_root(self, status_id):
        status = self.tweets.get(doc_id=int(status_id))

        if status:
            parent_id = status['parent_id']
        else:
            print(f"Couldn't find #{status_id} (status probably deleted)")
            return

        if parent_id:
            return self.find_root(parent_id)
        else:
            return status_id
    
    # gets the corresponding agreement from the root of a status
    def find_agreement(self, status_id):
        agreement_status_id = self.find_root(status_id)
        agreement = self.threads.get(
            where('status_id') == agreement_status_id
        )

        return agreement

    # custom operation function for tinydb inserts a signature into an agreement
    def add_signature(self, name, status_id):
        def transform(doc):
            doc['signatures'][name] = status_id
        return transform
    
    # custom operation function for tinydb inserts new links into an agreement
    def add_links(self, links):
        def transform(doc):
            doc['links'].extend(links)
        return transform
    
    # custom operation function for tinydb inserts a child's id to it's parent
    def add_child_link(self, child_id):
        def transform(doc):
            doc['child_ids'].append(child_id)
        return transform

    def extract_links(self, text):
        # extracts links from text using regex
        tco_links = re.findall(r"(https?://[a-zA-Z0-9.-/]+)(?:\W|$)", text)
        
        # twitter shortens links to t.co, this follows the redirect to the original link
        original_links = []
        for l in tco_links:
            try:
                clean_link = requests.head(l).headers.get('location')
                original_links.append(clean_link)
            except requests.exceptions.RequestException as e:
                print(f'Requests link redirect error: {e}')
                original_links.append(l)
        
        return original_links

    def parse(self, status, api):
        text = status['text']

        users = [status["user_screen_name"]] # initialized to include author
        is_root = (status["parent_id"] == None)
        status_id = str(status.doc_id)
        parent_id = status["parent_id"]

        # makes sure old tweet isn't reparsed
        if status['parsed'] == True:
            return

        # adding link from parent to child
        int_parent_id = 0
        if parent_id:
            int_parent_id = int(parent_id)
        if int_parent_id in self.tweets._read_table().keys():
            self.tweets.update(
                self.add_child_link(status_id),
                doc_ids=[int(parent_id)]
            )

        # extracts consecutive users from the beginning of the tweet
        for word in text.split():
            if word[0] == '@':
                if word != '@agreementengine':
                    users.append(word[1:])
            else:
                break

        

        # pushes valid agreements to threads
        # (current valid agreement only requires being a root tweet containing @agreementengine)
        if is_root:
            # parsing for enforcer
            result = re.search(r"enforced by @(\w+)(\W|$)", text)
            if result:
                enforcer = result.groups()[0]
            else:
                enforcer = status["user_screen_name"]

            thread_id = self.threads.insert({
                "author": status["user_full_name"],
                "enforcer": enforcer,
                "members": users,
                "text": text,
                "signatures": {},
                "dead": False,
                "links": self.extract_links(text),
                "status_id": status_id,
                "status_link": f"https://twitter.com/{status['user_screen_name']}/status/{status_id}"
            })

            # replies to an agreement creation tweet with a link to the agreement
            # api.update_status(f"@{status['user_screen_name']} Your agreement has been created! http://localhost/thread/{thread_id}", status_id)

            # thread id has to be set after agreement created
            self.tweets.update(
                {'thread_id': thread_id},
                doc_ids=[int(status_id)]
            )

            # current num threads for api call updated
            self.threads.update(
                {'num_threads': thread_id},
                doc_ids=[0]
            )

        # sets the thread id of a status (0 if no corresponding agreement)
        found_agreement = self.find_agreement(status_id)

        if found_agreement:
            agreement_id = found_agreement.doc_id
        else:
            agreement_id = 0    

        self.tweets.update(
            {'thread_id': agreement_id},
            doc_ids=[int(status_id)]
        )

        if found_agreement:
            if status["user_screen_name"] in found_agreement["members"]:
                # signing agreement
                if "sign" in text:
                    print('signed')
                    # adding signature to agreement
                    self.threads.update(
                        self.add_signature(status["user_screen_name"], status_id),
                        doc_ids=[found_agreement.doc_id]
                    )
                
                # leaving agreement
                if ("+leave" in text) or ("+unsign" in text):
                    # marking thread dead
                    self.threads.update(
                        {"dead": True},
                        doc_ids=[found_agreement.doc_id]
                    )
            else:
                print(f'Action #{status_id} not by member of agreement')
            
            # adding links from child statuses
            if not is_root:
                links = self.extract_links(text)
                if links:
                    self.threads.update(
                        self.add_links(links),
                        doc_ids=[found_agreement.doc_id]
                    )

        # sets tweet status to parsed
        self.tweets.update(
                {'parsed': True},
                doc_ids=[int(status_id)]
            )
        

    def parse_all(self, api):
        # using internal function to retrieve tweet table's keys
        status_ids = list(self.tweets._read_table().keys())
        status_ids.sort()

        # parses unparsed tweets in chronological order (sorted)
        for s in status_ids:
            status = self.tweets.get(doc_id=s)
            if status['parsed'] == False:
                self.parse(status, api)