from app.core import db
from tinydb.database import Document

class Account:
    def __init__(self, user):
        self.account_table = db.table('accounts')
        self.id = user.id
        self.user = user
    
    def in_database(self):
        return self.account_table.contains(doc_id=self.id)
    
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

        def increment_num_accounts(doc):
            num_accounts = int(doc['num_accounts'])
            num_accounts += 1
            doc['num_accounts'] = str(num_accounts)

        self.account_table.update(
            increment_num_accounts, 
            doc_ids=[0]
        )