from app.core import api, db
from tinydb.database import Document

class Account:
    def __init__(self, user):
        self.account_table = db.table('accounts')
        self.id = user.id
        self.user = user

        if self.account_table.contains(doc_id=self.id):
            self.add_to_database()
    
    def add_to_database(self):
        # initializing default account data
        entry = {
            'full_name': self.user.name,
            'screen_name': self.user.screen_name,
            'balance': '0',
            'contracts': []
        }

        # inserting account data into table
        self.account_table.insert(Document(
            entry, 
            doc_id=self.id
        ))

        # updating number of accounts
        num_accounts = int(self.account_table.get(doc_id=0))
        num_accounts += 1

        self.account_table.update(
            {'num_accounts': str(num_accounts)}, 
            doc_ids=[0]
        )