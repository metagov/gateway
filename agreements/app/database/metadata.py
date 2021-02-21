from tinydb.database import Document
from tinydb import where
import json, logging

# container for metadata in the tinydb database
class Metadata:
    def __init__(self, db):
        self.db = db
        self.table = db.table('metadata')
        self.logger = logging.getLogger(__name__)

        # initializes metadata table in database if it hasn't been created yet
        if not self.table.contains(doc_id=1):
            self.initialize_database()

    def initialize_database(self):
        self.logger.info('Database is empty, loading default configuration')
        config = json.load(open('app/database/default_config.json', 'r'))
        config['last_status_parsed'] = config['genesis_status']
        
        self.table.insert(Document(config, doc_id=1))

    # retrieves a value from the metadata dictionary
    def retrieve(self, tag):
        text = self.table.get(doc_id=1)[tag]

        # converts to integer or float as needed
        try:
            val = int(text)
        except ValueError:
            try:
                val = float(text)
            except ValueError:
                return
        
        return val

    # updates a value in the metadata dictionary
    def update(self, tag, value):
        self.table.update(
            {tag: str(value)},
            doc_ids=[1]
        )