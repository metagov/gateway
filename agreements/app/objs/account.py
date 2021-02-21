from app import core
from tinydb.database import Document
from . import contract
import logging
import tweepy

# represents a single account
class Account:
    def __init__(self, arg):
        self.account_table = core.db.table('accounts')
        self.logger = logging.getLogger(".".join([self.__module__, type(self).__name__]))

        # can be initialized with a user id integer, attempts to find account entry in db
        if type(arg) == int:
            self.id = arg
            if not self.in_database():
                self.logger.warn('Account does not exist, unable to generate (user object not provided)')

        # can be initialized with a tweepy user object, generates new db entry if doesn't already exist
        elif type(arg) == tweepy.models.User:
            user = arg
            self.id = user.id
            if not self.in_database():
                self.generate(user)
        else:
            self.logger.warn('Invalid parameter when creating Account')

        self.screen_name = self.get_entry()['screen_name']

    # returns dict from db
    def get_entry(self):
        return self.account_table.get(doc_id=self.id)

    # checks if user id is already in db
    def in_database(self):
        return self.account_table.contains(doc_id=self.id)
    
    # generates a new account
    def generate(self, user):
        # initializing default account data
        entry = {
            'full_name': user.name,
            'screen_name': user.screen_name,
            'balance': '0',
            'contracts': [],
            'likes': [],
            'retweets': []
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
    
    # modifies account balance
    def change_balance(self, user_id, amount):
        # passed into tiny db update function, adds to balance
        def add_to_balance(doc):
            doc['balance'] = str(int(doc['balance']) + amount)
        
        # updates account balance
        self.account_table.update(
            add_to_balance,
            doc_ids=[user_id]
        )        

    # checks whether a user has had a like contract called in on a status
    def has_liked(self, status_id):
        likes = self.get_entry()['likes']
        return str(status_id) in likes
    
    # checks whether a user has had a retweet contract called in on a status
    def has_retweeted(self, status_id):
        retweets = self.get_entry()['retweets']
        return str(status_id) in retweets

    # generates a new contract
    def create_contract(self, status):
        self.logger.info(f'Generating new contract for {self.screen_name} [{self.id}]')

        # created contract object
        new_contract = contract.Contract(status)
        total_value = new_contract.generate()

        if total_value == False:
            self.logger.warn('Exiting invalid contract')
        
        else:
            # calculates taxed amount and amount to pay users based on total value of contract
            to_pay_engine = round(total_value * core.Consts.tax_rate)
            to_pay_user = total_value - to_pay_engine

            # paid out to user and agreement engine
            self.change_balance(core.engine_id, to_pay_engine)
            self.change_balance(self.id, to_pay_user)
            self.logger.info(f'Paid {self.screen_name} [{self.id}] {to_pay_user} XSC ({to_pay_engine} withheld)')

            # adds contract id to account list
            self.account_table.update(
                lambda d: d['contracts'].append(str(status.id)),
                doc_ids=[self.id]
            )

        # generating message to send to user
        c_entry = new_contract.get_entry()
        update_message = ''

        if new_contract.oversized == True:
            update_message = f'You have reached your contract limit and cannot generate new ones until they have been used up.'
        elif new_contract.resized == True:
            update_message = f'Your request exceeded your {c_entry["type"]} contract limit so it was resized. Your account has been credited {to_pay_user} XSC for this {c_entry["count"]} {c_entry["type"]} contract.'
        else:
            update_message = f'Successfully generated! Your account has been credited {to_pay_user} XSC for this {c_entry["count"]} {c_entry["type"]} contract.'

        # post to twitter
        core.api.update_status(
            status = f'@{self.screen_name} ' + update_message, 
            in_reply_to_status_id = status.id, 
            auto_populate_reply_metadata= True)

    # executes contracts on a requested post for a certain amount of XSC
    def execute_contracts(self, status):
        self.logger.info(f'Executing contracts for {self.screen_name} [{self.id}]')

        text = status.full_text 
        arg = text[text.find("+exe"):].split()[1]

        # extracting amount to spend
        try:
            to_spend = int(arg)
        except ValueError:
            return False
        
        # executed on the post being replied to (ie reply to post you want to execute contracts on)
        executing_on = status.in_reply_to_status_id

        self.logger.info(f'New execution request spending {to_spend} XSC on status #{executing_on}')

        contract_pool = contract.Pool()
        # auto execute function will try to spend all of the funds requested executing contracts
        executed_count, amount_spent = contract_pool.auto_execute_contracts(self.id, executing_on, to_spend)

        # updates balance based on amount actually spent
        self.change_balance(self.id, -amount_spent)

        if executed_count > 0:
            update_message = f'Executed {executed_count} contracts for {amount_spent} XSC.'
        else:
            update_message = f'Unable to execute any contracts, your account has not been charged.'

        # posting message to twitter
        core.api.update_status(
            status = f'@{self.screen_name} ' + update_message, 
            in_reply_to_status_id = status.id, 
            auto_populate_reply_metadata= True)



