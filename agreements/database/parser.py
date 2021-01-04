from tinydb.database import Document
from tinydb import where
import re

class Parser:
    def __init__(self, db):
        self.db = db
        self.tweets = db.table('tweets')
        self.threads = db.table('threads')

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
            'parsed_type': '',                           # agreement, amendment, or discussion
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
    def add_signature(self, name, status_id, amendment_id=0):
        def transform(doc):
            if amendment_id:
                # attempts to sign an agreement's amendment
                amendment = doc['amendments'].__contains__(str(amendment_id))
                if amendment:
                    amendment['signatures'][name] = status_id
            else:
                # signs agreement
                doc['signatures'][name] = status_id
        return transform

    def parse(self, status):
        text = status['text']

        terms = {}
        term_nums = []
        keywords = []
        users = [status["user_screen_name"]] # initialized to include author
        is_root = (status["parent_id"] == None)
        status_id = status.doc_id
        parent_id = status["parent_id"]
        has_terms = False

        # extracts consecutive users from the beginning of the tweet
        for word in text.split():
            if word[0] == '@':
                if word != '@agreementengine':
                    users.append(word[1:])
            else:
                break
        
        # parsing by line
        for line in text.splitlines():
            # checks if a line is a numbered term (ex: "1. ")
            result = re.search(r'^(\d+)\. ', line)
            if result:
                has_terms = True
                # these lines look complicated, but all they do is convert
                # "1. term line text" -> {1: "term line text"}
                term_num = int(result.group(1))
                term_txt = line[len(result.group(0)):]

                terms.update(
                    {term_num: term_txt}
                )

                # keeps track of term line numbers in case they are non sequential
                term_nums.append(term_num)
                term_nums.sort()

            # locates bot commands with "+" prefix
            else:
                for word in line.split():
                    if word[0] == "+":
                        keywords.append(word[1:])

        # -------------------------------------------------------------------------------
        # adding data to in tweets table that links to threads table
        # -------------------------------------------------------------------------------

        # setting parsed type
        parsed_type = ""
        if "agreement" in keywords:
            parsed_type = "agreement"
        elif "amendment" in keywords:
            parsed_type = "amendment"
        else:
            parsed_type = "discussion"
        
        # adding parsed type to status entry
        self.tweets.update(
            {'parsed_type': parsed_type},
            doc_ids=[status_id]
        )

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

        # ------------------------------------------------------------------------------
        # evaluating commands 
        # ------------------------------------------------------------------------------

        # pushes valid agreements to threads
        if "agreement" in keywords:
            if is_root and has_terms:
                thread_id = self.threads.insert({
                    "author": status["user_full_name"],
                    "members": users,
                    "terms": terms,
                    "term_nums": term_nums,
                    "signatures": {},
                    "amendments": {},
                    "status_id": status_id
                })
                
                # thread id has to be set after agreement created
                self.tweets.update(
                    {'thread_id': thread_id},
                    doc_ids=[status_id]
                )

            else:
                print('Malformed agreement')
                return
        
        # responsible for finding the correct object to sign based on reply
        if "sign" in keywords:
            # sets the status to sign, this will be the status being replied to
            # or in the case of an agreement it will be the status itself
            if is_root:
                to_sign = status_id
            else:
                to_sign = parent_id
            
            # retrieves agreement status is associated with
            agreement = self.find_agreement(to_sign)

            if agreement:
                # signing agreeement case
                if agreement['status_id'] == to_sign:
                    self.threads.update(
                        self.add_signature(status["user_screen_name"], status_id),
                        where('status_id') == to_sign
                    )
            else:
                print(f'Signature #{status_id} not associate with a valid agreement')


    def parse_all(self):
        # using internal function to retrieve tweet table's keys
        status_ids = list(self.tweets._read_table().keys())
        status_ids.sort()

        # parses unparsed tweets in chronological order (sorted)
        for s in status_ids:
            status = self.tweets.get(doc_id=s)
            if status['parsed'] == False:
                self.parse(status)