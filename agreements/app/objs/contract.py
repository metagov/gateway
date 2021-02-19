from app import core
from tinydb.database import Document
from tinydb import where

class Pool:
    def __init__(self):
        self.contract_table = core.db.table('contracts')
    
    def count_user_contracts(self, contract_type, user_id):
        contract_count = 0

        for contract in self.contract_table.search(
            where('user') == str(user_id)):

            if contract['type'] == contract_type:
                contract_count += int(contract['count'])

        return contract_count


class Contract:
    def __init__(self, status):
        self.contract_table = core.db.table('contracts')
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

        total_cost = unit_cost * contract_size

        return total_cost

    
