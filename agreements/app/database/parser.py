from tinydb.database import Document
from .metadata import Metadata

class Parser:
    def __init__(self, db, api):
        self.db = db
        self.api = api
        self.meta = Metadata(db)
        self.accounts = db.table('accounts')
        self.contracts = db.table('contracts')
        self.statuses = db.table('statuses')

        # intializing accounts table
        if not self.accounts.contains(doc_id=0):
            self.accounts.insert(Document(
                {
                    'num_accounts': '0'
                },
                doc_id=0))
        
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
        self.add_account(status)

        text = status.full_text

        if "+gen" in text:
            self.generate(status)
        if "+exe" in text:
            self.execute(status)

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

    def add_account(self, status):
        if self.accounts.contains(doc_id=status.user.id):
            return False

        account = {
            'full_name': status.user.name,
            'screen_name': status.user.screen_name,
            'balance': '0',
            'contracts': []
        }

        self.accounts.update(
            {'num_accounts': str(int(self.accounts.get(doc_id=0)['num_accounts']) + 1)},
            doc_ids=[0]
        )

        self.accounts.insert(Document(
            account,
            doc_id=status.user.id
        ))

        return True
    
    def generate(self, status):
        # determines how many like and retweet contracts are being generated
        text = status.full_text
        words = text[text.find("+gen"):].split()
        arg = words[1]

        if (arg[-1] == "L") or (arg[-1] == "l"):
            gen_type = "like"

        elif (arg[-1] == "R") or (arg[-1] == "r"):
            gen_type = "retweet"
        
        try:
            count = int(arg[:-1])
        except ValueError:
            return

        type_limit = self.meta.retrieve(f'{gen_type}_limit')
        type_value = self.meta.retrieve(f'{gen_type}_value')

        # cannot create over the limit
        # THIS SHOULD BE FROM THE CONTRACT POOL. UPDATE LATER WHEN POSSIBLE.
        if count > type_limit: count = type_limit
        
        # retrieving user follower count to approximate social value
        user = self.api.get_user(status.user.id)
        followers = user.followers_count

        # calculating cost per unit of contract
        unit_cost = count * type_value * followers

        contract = {
            "state": "alive",
            "user": str(user.id),
            "type": gen_type,
            "count": str(count),
            "price": str(unit_cost),
            "created": str(status.created_at),
            "executed": [

            ]
        }

        self.contracts.insert(Document(
            contract,
            doc_id=status.id
        ))

        print (contract)