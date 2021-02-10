from tinydb.database import Document
from tinydb import where
import json

# container for metadata in the tinydb database
class Metadata:
    def __init__(self, db):
        self.db = db
        self.table = db.table('metadata')

        # initializes metadata table in database if it hasn't been created yet
        if not self.table.contains(doc_id=1):
            self.initialize_database()

    def initialize_database(self):
        config = json.load(open('app/database/default_config.json', 'r'))
        config['last_status_parsed'] = config['genesis_status']
        
        self.table.insert(Document(config, doc_id=1))

    # retrieves a value from the metadata dictionary
    def retrieve(self, tag):
        return int(self.table.get(doc_id=1)[tag])

    # updates a value in the metadata dictionary
    def update(self, tag, value):
        self.table.update(
            {tag: str(value)},
            doc_ids=[1]
        )