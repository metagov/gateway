from tinydb.database import Document
from tinydb.operations import *

class Digester:
    def __init__(self, db):
        self.db = db
        self.table = db.table('tweets')

    def add(self, status):
        # ensures tweet hasn't been added before
        if self.table.contains(doc_id=status.id):
            print(f'Status #{status.id} already in database')
            return

        # recording data to store in database
        tweet = {
            'text':      status.full_text,              # text of the tweet
            'user_name': status.user.screen_name,       # user name of poster
            'user_id':   status.user.id,                # user id of poster
            'parent_id': status.in_reply_to_status_id,  # id of tweet replying
            'created':   str(status.created_at)         # date and time created
        }

        # inserts data into database under the tweet's id
        self.table.insert(
            Document(
                tweet, 
                doc_id=status.id
            )
        )


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