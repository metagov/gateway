from tinydb.database import Document
from tinydb import where
import re

def add_signature(name, status_id):
    def transform(doc):
        doc['signatures'][name] = status_id
    return transform

class Parser:
    def __init__(self, db):
        self.db = db
        self.tweets = db.table('tweets')
        self.threads = db.table('threads')

        if not self.threads.get(doc_id=1):
            self.threads.insert({})

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
            'user_id':   status.user.id,                 # user id of poster
            'created':   str(status.created_at),         # date and time created
            'parent_id': status.in_reply_to_status_id    # id of tweet replying
        }

        # inserts data into database under the tweet's id
        self.tweets.insert(
            Document(
                tweet, 
                doc_id=status.id
            )
        )
    
    def parse(self, status):
        text = status['text']

        terms = {}
        term_nums = []
        keywords = []
        users = [status["user_screen_name"]]
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

        agreement = {
            "author": status["user_full_name"],
            "members": users,
            "keywords": keywords,
            "terms": terms,
            "term_nums": term_nums,
            "signatures": {},
            "amendments": [],
            "status_id": status_id
        }

        if is_root and has_terms:
            self.threads.insert(agreement)

        if "sign" in keywords:
            if is_root:
                self.threads.update(
                    add_signature(status["user_screen_name"], status_id),
                    where('status_id') == status_id
                )

            else:
                self.threads.update(
                    add_signature(status["user_screen_name"], status_id),
                    where('status_id') == parent_id
                )
                # for t in self.threads:
                #     print(t)
                # print(parent_id == 1343978594649911297)
                # print(self.threads.get(where('status_id') == parent_id))
                # print(parent_id)
                # print(status["user_screen_name"])
                # print()
                # print(self.threads.search(where('status_id') == parent_id))



        
                


# container for metadata in the tinydb database
class Metadata:
    def __init__(self, db):
        self.db = db
        self.table = db.table('metadata')

        # initializes metadata table in database if it hasn't been created yet
        if not self.table.contains(doc_id=1):
            self.table.insert(Document(
                {
                    'last_status_parsed': 1
                }, 
                doc_id=1))

    # retrieves a value from the metadata dictionary
    def retrieve(self, tag):
        return self.table.get(doc_id=1)[tag]

    # updates a value in the metadata dictionary
    def update(self, tag, value):
        self.table.update(
            {tag: value},
            doc_ids=[1]
        )