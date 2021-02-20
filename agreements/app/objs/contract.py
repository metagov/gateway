from app import core
from tinydb.database import Document
from tinydb import where
import logging

class Pool:
    def __init__(self):
        self.contract_table = core.db.table('contracts')
        self.logger = logging.getLogger(".".join([self.__module__, type(self).__name__]))
    
    def count_user_contracts(self, contract_type, user_id):
        contract_count = 0

        # searches all contracts made by specified user
        for contract in self.contract_table.search(
            where('user') == str(user_id)):

            # if contract is of requested type, contract count is updated
            if contract['type'] == contract_type:
                contract_count += int(contract['count'])

        return contract_count

    def auto_execute_contracts(self, user_id, status, amount):
        balance = amount
        contract_dict = self.contract_table._read_table()
        # ids are ordered from oldest to newest (excluding zero entry containing metadata)
        contract_ids = list(contract_dict.keys())[1:]

        for c_id in contract_ids:
            c_entry = contract_dict[c_id]
            c_price = int(c_entry['price'])
            c_user_id = int(c_entry['user'])

            # prevents user from executing their own contract
            if user_id == c_user_id:
                continue

            # executes contract if it can be paid for
            if c_price <= balance:
                self.execute(c_id, status)
                balance -= c_price

            # stops trying to execute when total amount is spent
            if balance == 0:
                break

        # returns the amount actually spent executing contracts
        return amount - balance

    def execute(self, contract_id, status):
        print(contract_id, "I have been executed!")

class Contract:
    def __init__(self, status):
        self.contract_table = core.db.table('contracts')
        self.logger = logging.getLogger(".".join([self.__module__, type(self).__name__]))
        self.id = status.id
        self.status = status
    
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

        if remaining_contracts < 1:
            self.logger.warn('User has exceeded contract limit')
            return False

        # if user requests more than allowed, resized to max possible
        if contract_size > remaining_contracts:
            contract_size = remaining_contracts

        # calculating unit cost per execution
        social_reach = self.status.user.followers_count
        unit_cost = contract_type_value * social_reach

        contract = {
            "state": "alive",
            "user": str(self.status.user.id),
            "type": contract_type,
            "count": str(contract_size),
            "price": str(unit_cost),
            "created": str(self.status.created_at),
            "executed": []
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

        total_cost = unit_cost * contract_size

        self.logger.info(f'New contract #{self.id} created for {contract_size} {contract_type}s valued at {total_cost} XSC')

        return total_cost

    
