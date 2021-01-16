from tinydb.database import Document
from tinydb import where
import re

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

        # recording data to store in database
        tweet = {
            'text': status.full_text,                    # text of the tweet
            'user_full_name': status.user.name,          # actual name of poster
            'user_screen_name': status.user.screen_name, # user name of poster
            'user_id': status.user.id,                   # user id of poster
            'created': str(status.created_at),           # date and time created
            'parent_id': status.in_reply_to_status_id,   # id of tweet replying
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
        status = self.tweets.get(doc_id=status_id)

        if status:
            parent_id = status['parent_id']
        else:
            print(f"Couldn't find #{status_id}")
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

    # custom operation function for tinydb inserts a signature into an agreement/amendment
    def add_signature(self, name, status_id):
        def transform(doc):
            doc['signatures'][name] = status_id
        return transform

    def parse(self, status):
        text = status['text']

        users = [status["user_screen_name"]] # initialized to include author
        is_root = (status["parent_id"] == None)
        status_id = status.doc_id
        parent_id = status["parent_id"]

        # makes sure old tweet isn't reparsed
        if status['parsed'] == True:
            return
        
        self.tweets.update(
            {'parsed': True},
            doc_ids=[status_id]
        )

        # extracts consecutive users from the beginning of the tweet
        for word in text.split():
            if word[0] == '@':
                if word != '@agreementengine':
                    users.append(word[1:])
            else:
                break

        # sets the thread id of a status (0 if no corresponding agreement)
        found_agreement = self.find_agreement(status_id)

        if found_agreement:
            agreement_id = found_agreement.doc_id
        else:
            agreement_id = 0    

        self.tweets.update(
            {'thread_id': agreement_id},
            doc_ids=[status_id]
        )

        # pushes valid agreements to threads
        # (current valid agreement only requires being a root tweet containing @agreementengine)
        if is_root:
            thread_id = self.threads.insert({
                "author": status["user_full_name"],
                "members": users,
                "text": text,
                "signatures": {},
                "dead": False,
                "status_id": status_id,
                "link": f"https://twitter.com/{status['user_screen_name']}/status/{status_id}"
            })
            
            # thread id has to be set after agreement created
            self.tweets.update(
                {'thread_id': thread_id},
                doc_ids=[status_id]
            )

            self.threads.update(
                {'num_threads': thread_id},
                doc_ids=[0]
            )

        # responsible for finding the correct object to sign based on reply
        if "+sign" in text:
            # retrieves agreement status is associated with
            agreement = self.find_agreement(status_id)

            if agreement:
                # ensures signature from a member of the agreement
                if status["user_screen_name"] in agreement["members"]:
                    # adding signature to agreement
                    self.threads.update(
                        self.add_signature(status["user_screen_name"], status_id),
                        doc_ids=[agreement.doc_id]
                    )
                else:
                    print(f'Signature #{status_id} not by member of agreement')

            else:
                print(f'Signature #{status_id} not associate with a valid agreement')
        
        # leaving or unsigning an agreement destroys it
        if ("+leave" in text) or ("+unsign" in text):
            agreement = self.find_agreement(status_id)

            if agreement:
                # ensures signature from a member of the agreement
                if status["user_screen_name"] in agreement["members"]:
                    # marking thread dead
                    self.threads.update(
                        {"dead": True},
                        doc_ids=[agreement.doc_id]
                    )
                else:
                    print(f'Leave request #{status_id} not by member of agreement')
            else:
                print(f'Leave request #{status_id} not associated with a valid agreement')



    def parse_all(self):
        # using internal function to retrieve tweet table's keys
        status_ids = list(self.tweets._read_table().keys())
        status_ids.sort()

        # parses unparsed tweets in chronological order (sorted)
        for s in status_ids:
            status = self.tweets.get(doc_id=s)
            if status['parsed'] == False:
                self.parse(status)