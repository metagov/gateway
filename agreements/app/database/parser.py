from tinydb.database import Document
from .metadata import Metadata
from app.objs import account, contract
from app.core import Consts

class Parser:
    def __init__(self, db, api):
        self.db = db
        self.api = api
        self.meta = Metadata(db)
        self.accounts = db.table('accounts')
        self.contracts = db.table('contracts')
        self.statuses = db.table('statuses')
        self.me = api.me()

        # intializing accounts table
        if not self.accounts.contains(doc_id=0):
            self.accounts.insert(Document(
                {
                    'num_accounts': '0'
                },
                doc_id=0))
            
            account.Account(self.me)
        
        # intializing contracts table
        if not self.contracts.contains(doc_id=0):
            self.contracts.insert(Document(
                {
                    'num_contracts': '0',
                    'total_value': '0',
                },
                doc_id=0))
    
    def parse(self, status):
        self.add_status(status)


        acc = account.Account(status.user)

        text = status.full_text

        if "+gen" in text:
            acc.generate_contract(status)
        if "+exe" in text:
            acc.execute_contracts(status)
                
    def add_status(self, status):
        if self.statuses.contains(doc_id=status.id):
            return

        dict_status = {
            'text': status.full_text,
            'user_full_name': status.user.name,
            'user_screen_name': status.user.screen_name,
            'user_id': str(status.user.id),
            'created': str(status.created_at),
            'parent_id': str(status.in_reply_to_status_id) if status.in_reply_to_status_id else None,
        }

        # adding status to database
        self.statuses.insert(Document(
            dict_status, 
            doc_id=status.id
        ))

        return True
    
    def pay(self, user, amount):
        # function definition to update database 
        def change_balance(doc):
            int_balance = int(doc['balance'])
            int_balance += amount
            doc['balance'] = str(int_balance)

        # applying change_balance function to give user amount of xsc
        self.accounts.update(
            change_balance,
            doc_ids=[user]
        )