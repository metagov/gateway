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
        self.agreements = db.table('agreements')
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
                    # 'total_value': '0',
                },
                doc_id=0))
        
        if not self.agreements.contains(doc_id=0):
            self.agreements.insert(Document(
                {
                    'num_agreements': '0'
                },
                doc_id=0))
    
    def parse(self, status):
        # decides what command a tweet is and runs the proper code
        self.add_status(status)
        text = status.full_text

        acc = account.Account(status.user)

        # generate and execute contract commands
        if "+gen" in text:
            acc.create_contract(status)
        elif "+exe" in text:
            acc.execute_contracts(status)
        elif "+bal" in text:
            acc.send_current_balance(status)
        elif "+likes" in text:
            acc.send_current_likes(status)
        elif "+retweets" in text:
            acc.send_current_retweets(status)
        elif "+agr" in text:
            acc.create_agreement(status)
        elif "+upheld" in text:
            acc.vote_upheld(status)
        elif "+broken" in text:
            acc.vote_broken(status)

    # adds data from every mention status to the database 
    def add_status(self, status):
        if self.statuses.contains(doc_id=status.id):
            return False

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