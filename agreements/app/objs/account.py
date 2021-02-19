from app import core
from tinydb.database import Document
from .contract import Contract

class Account:
    def __init__(self, user):
        self.account_table = core.db.table('accounts')
        self.id = user.id
        self.user = user

        if not self.in_database():
            self.add_to_database()
    
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
    
    def pay_generate(self, user_id, amount):
        # passed into tiny db update function, adds to balance
        def add_to_balance(doc):
            balance = int(doc['balance'])
            balance += amount
            doc['balance'] = str(balance)
        
        # updates account balance
        self.account_table.update(
            add_to_balance,
            doc_ids=[user_id]
        )

    def pay_transfer(self, user_id, amount):
        pass

    def generate_contract(self, status):
        new_contract = Contract(status)
        total_value = new_contract.generate()
        # calculates taxed amount and amount to pay users based on total value of contract
        to_pay_engine = round(total_value * core.Consts.tax_rate)
        to_pay_user = total_value - to_pay_engine

        print(to_pay_engine, to_pay_user)

        self.pay_generate(core.engine_id, to_pay_engine)
        self.pay_generate(self.id, to_pay_user)
        

