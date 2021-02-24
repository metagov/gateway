from app import core
from tinydb.database import Document
from tinydb import where
import logging
from . import account

# represents the contract pool
class Pool:
    def __init__(self):
        self.contract_table = core.db.table('contracts')
        self.logger = logging.getLogger(".".join([self.__module__, type(self).__name__]))
    
    # counts how many contracts a user has for a given type
    def count_user_contracts(self, contract_type, user_id):
        contract_count = 0

        # searches all contracts made by specified user
        for contract in self.contract_table.search(where('user_id') == str(user_id)):
            # if contract is of requested type, contract count is updated
            if contract['type'] == contract_type:
                contract_count += int(contract['count'])

        return contract_count

    # automatically executes contracts up to the amount specified on the given status
    def auto_execute_contracts(self, user_id, status, amount):
        balance = amount
        contract_dict = self.contract_table._read_table()
        # ids are ordered from oldest to newest (excluding zero entry containing metadata)
        contract_ids = list(contract_dict.keys())[1:]

        contract_count = 0

        for c_id in contract_ids:
            c_entry = contract_dict[c_id]
            c_price = int(c_entry['price'])
            c_user_id = int(c_entry['user_id'])
            c_type = c_entry['type']
            c_count = int(c_entry['count'])
            c_state = c_entry['state']

            if c_state == "dead":
                continue

            # prevents user from executing their own contract
            if user_id == c_user_id:
                continue

            # a user can't like or retweet the same post twice
            acc = account.Account(c_user_id)
            if (c_type == "like") and (acc.has_liked(status)):
                continue
            if (c_type == "retweet") and (acc.has_retweeted(status)):
                continue

            # executes contract if it can be paid for
            if c_price <= balance:
                if c_count > 0:
                    self.execute(c_id, status)
                    # adds status to likes or retweets list of an account
                    core.db.table('accounts').update(
                        lambda d: d[f'{c_type}s'].append(str(status)),
                        doc_ids=[c_user_id]
                    )
                    # updates remaining balance
                    balance -= c_price
                    contract_count += 1
                else:
                    def kill_contract(doc):
                        doc['state'] = 'dead'
                    self.contract_table.update(
                        kill_contract,
                        doc_ids=[c_id]
                    )

            # stops trying to execute when total amount is spent
            if balance == 0:
                break
        
        if contract_count > 0:
            self.logger.info(f'Successfully executed {contract_count} contracts for {amount - balance}/{amount} XSC')
        else:
            self.logger.info('Was not able to execute any contracts')

        # returns the number of contracts executed and the amount actually spent executing contracts
        return (contract_count, amount - balance)

    # actual execution of a single contract on a status
    def execute(self, contract_id, status_id):
        contract_dict = self.contract_table._read_table()
        to_execute = contract_dict[contract_id]
        c_price = to_execute['price']
        c_type = to_execute['type']
        c_user_id = to_execute['user_id']
        c_user_screen_name = to_execute['user_screen_name']

        status = core.api.get_status(status_id)

        self.logger.info(f'Executed {c_type} contract #{contract_id} from {c_user_screen_name} [{c_user_id}] for {c_price} XSC')

        if core.Consts.send_tweets:
            # sends out message calling in executed contract
            core.api.update_status(
                status = f'@{c_user_screen_name} Your contract has been called in, please {c_type} the above post!' + " #" + str(status_id), 
                in_reply_to_status_id = status_id, 
                auto_populate_reply_metadata= True)
        else:
            print(f'@{c_user_screen_name} Your contract has been called in, please {c_type} the above post!' + " #" + str(status_id))
        
        # transform function to update contract use count and executions
        def update_contract(status_id):
            def transform(doc):
                doc['count'] = str(int(doc['count']) - 1)
                doc['executed_on'].append(status_id)
            return transform
        self.contract_table.update(
            update_contract(status_id),
            doc_ids=[contract_id]
        )

# represents a single contract
class Contract:
    def __init__(self, status):
        self.contract_table = core.db.table('contracts')
        self.logger = logging.getLogger(".".join([self.__module__, type(self).__name__]))
        self.id = status.id
        self.status = status

        # attributes show whether a generationg request exceeded the limit, and whether it could be resized to under the limit
        self.resized = False
        self.oversized = False
    
    # returns dict entry from db
    def get_entry(self):
        return self.contract_table.get(doc_id=self.id)

    def generate(self):
        text = self.status.full_text
        arg = text[text.find("+gen"):].split()[1]

        # detecting contract type (like or retweet)
        if (arg[-1] == "L") or (arg[-1] == "l"):
            contract_type = "like"
        elif (arg[-1] == "R") or (arg[-1] == "r"):
            contract_type = "retweet"
        
        # trying to extract contract size
        try:
            contract_size = int(arg[:-1])
        except ValueError:
            logger.warn('Could not parse generate command')
            return False
        
        return self.complex_generate(contract_type, contract_size)

    # generates a contract from a status (given in initialization)
    def complex_generate(self, contract_type, contract_size):
        # selecting proper consts based on contract type
        if contract_type == "like":
            contract_type_limit = core.Consts.like_limit
            contract_type_value = core.Consts.like_value
        elif contract_type == "retweet":
            contract_type_limit = core.Consts.retweet_limit
            contract_type_value = core.Consts.retweet_value
        
        # determines how many more contracts a user can generate
        contract_pool = Pool()
        total_contracts = contract_pool.count_user_contracts(contract_type, self.status.user.id)
        remaining_contracts = contract_type_limit - total_contracts 

        # user has gone over the max contract limit for a particular type
        if remaining_contracts < 1:
            self.logger.warn('User has exceeded contract limit')
            self.oversized = True
            return False

        # if user requests more than allowed, resized to max possible
        if contract_size > remaining_contracts:
            self.logger.warn('New contract will exceed limit, resizing')
            contract_size = remaining_contracts
            self.resized = True

        # calculating unit cost per execution
        social_reach = self.status.user.followers_count
        unit_cost = contract_type_value * social_reach

        # generating dict to be entered into db
        contract = {
            "state": "alive",
            "user_id": str(self.status.user.id),
            "user_screen_name": self.status.user.screen_name,
            "type": contract_type,
            "count": str(contract_size),
            "price": str(unit_cost),
            "created": str(self.status.created_at),
            "executed_on": []
        }

        # inserting into database
        self.contract_table.insert(Document(
            contract, doc_id=self.status.id
        ))

        # updating number of contracts
        def increment_num_contracts(doc):
            num_contracts = int(doc['num_contracts'])
            num_contracts += 1
            doc['num_contracts'] = str(num_contracts)
        self.contract_table.update(
            increment_num_contracts, 
            doc_ids=[0]
        )

        # calculating total cost
        total_cost = unit_cost * contract_size

        self.logger.info(f'New contract #{self.id} created for {contract_size} {contract_type}s valued at {total_cost} XSC')
        self.logger.info(contract)

        return total_cost

    
