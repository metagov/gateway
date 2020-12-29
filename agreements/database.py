from tinydb.database import Document
from tinydb.operations import *

# container for metadata in the tinydb database
class Metadata:
    def __init__(self, db):
        self.db = db

        # initializes metadata entry in database if it hasn't been created yet
        if not self.db.contains(doc_id=0):
            self.db.insert(Document(
                {
                    'last_status_parsed': 1
                }, 
                doc_id=0))

    # retrieves metadata dict from tinydb
    def get_data(self):
        return self.db.get(doc_id=0)

    def get_last_status_parsed(self):
        return self.get_data()['last_status_parsed']

    def set_last_status_parsed(self, id):
        self.db.update(
            set('last_status_parsed', id),
            doc_ids=[0]
        )