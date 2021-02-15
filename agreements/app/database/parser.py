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
            con = contract.Contract(status)
            con.generate()
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
        
        # retrieving consts from db
        if gen_type == "like":
            type_limit = Consts.like_limit
        else:
            type_limit = Consts.retweet_limit
        # type_limit = self.meta.retrieve(f'{gen_type}_limit')
        type_value = self.meta.retrieve(f'{gen_type}_value')
        tax_rate = self.meta.retrieve('tax_rate')

        # =============================================================================
        # calculating and generating contract json

        # cannot create contract over the limit
        # THIS SHOULD BE FROM THE CONTRACT POOL. UPDATE LATER WHEN POSSIBLE.
        if count > type_limit: count = type_limit
        
        # retrieving user follower count to approximate social value
        user = self.api.get_user(status.user.id)
        followers = user.followers_count

        # calculating cost per unit of contract
        unit_cost = type_value * followers

        contract = {
            "state": "alive",
            "user": str(user.id),
            "type": gen_type,
            "count": str(count),
            "price": str(unit_cost),
            "created": str(status.created_at),
            "executed": []
        }

        self.contracts.insert(Document(
            contract,
            doc_id=status.id
        ))

        # ===============================================================================
        # paying out to user, and reserving tax

        total_value = count * unit_cost
        # rounded to keep XSC in whole units
        taxed_value = round(total_value * tax_rate)
        to_pay_out = total_value - taxed_value

        self.pay(user.id, to_pay_out)
        self.pay(self.me.id, taxed_value)

        print(f'Generated contract {status.id} valued at {total_value}, {to_pay_out} paid out.')
    
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