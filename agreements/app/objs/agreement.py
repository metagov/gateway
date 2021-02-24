from app import core
from tinydb.database import Document
import logging, math
import tweepy
from . import contract

class Agreement:
    def __init__(self, arg):
        self.agreement_table = core.db.table('agreements')
        self.logger = logging.getLogger(".".join([self.__module__, type(self).__name__]))
        self.valid = False
        self.balance_limited = False
        self.contract_limited = False
        
        if type(arg) == int:
            self.id = arg
            if self.in_database():
                self.valid = True
            else:
                self.logger.warn('Agreement does not exist, unable to generate (status not provided)')

        elif type(arg) == tweepy.models.Status:
            status = arg
            self.id = status.id
            self.status = status
            self.valid = True

        else:
            self.logger.warn('Invalid parameter when creating Agreement')

    def get_entry(self):
        return self.agreement_table.get(doc_id=self.id)

    def in_database(self):
        return self.agreement_table.contains(doc_id=self.id)

    # generates a new agreement
    def generate(self, account):
        text = self.status.full_text
        arg = text[text.find("+agr"):].split()[1]

        # establishing contract type from tweet args
        if (arg[-1] == "L") or (arg[-1] == "l"):
            collateral_type = "like"
        elif (arg[-1] == "R") or (arg[-1] == "r"):
            collateral_type = "retweet"
        else:
            collateral_type = "xsc"
        
        # extracts all users mentioned in tweet
        users = self.status.entities['user_mentions']

        # the first other user becomes the "member" opposite the "creator"
        if len(users) <= 1:
            self.logger.warn('Agreement does not contain other members')
            self.valid = False
            return False
        else:
            member = users[1]
        
        # attempts to pay with existing balance
        if collateral_type == "xsc":
            try:
                collateral = int(arg)
            except ValueError:
                self.logger.warn('Could not parse agreement command')
                self.valid = False
                return False
            
            if collateral > account.check_balance():
                self.logger.warn('Insufficient balance to pay agreement collateral')
                self.balance_limited = True
                return False
            else:
                # removes funds from account balance
                account.change_balance(account.id, -collateral)
                self.logger.info(f'Removed {collateral} XSC of collateral from the balance of {account.screen_name} [{account.id}]')
        
        # if user is paying with likes or retweets, the contract will only be created if the agreement is broken
        else:
            try:
                collateral = int(arg[:-1])
            except ValueError:
                logger.warn('Could not parse agreement command')
                self.valid = False
                return False

            self.logger.info(f'Generating new contract for {account.screen_name} [{account.id}] (agreement context)')
                
            status = core.api.get_status(self.id)

            # creates new contract
            con = contract.Contract(status)
            total_value = con.complex_generate(collateral_type, collateral)

            if con.resized or con.oversized:
                self.logger.warn('Contract limit reached when creating agreement')
                self.contract_limited = True
                return False

            # contract will not be activated unless the agreement is broken
            con.contract_table.update(
                {'state': 'dead'},
                doc_ids=[self.id]
            )

        entry = {
            "state": "open",
            "creator_id": str(account.id),
            "creator_screen_name": account.screen_name,
            "creator_ruling": "",
            "member_id": member['id_str'],
            "member_screen_name": member['screen_name'],
            "member_ruling": "",
            "collateral_type": collateral_type,
            "collateral": str(collateral),
            "created": str(self.status.created_at),
            "text": text
        }

        # adding agreement to db
        self.agreement_table.insert(Document(
            entry, doc_id=self.id
        ))

        # updating number of agreements
        def increment_num_agreements(doc):
            num_agreements = int(doc['num_agreements'])
            num_agreements += 1
            doc['num_agreements'] = str(num_agreements)
        self.agreement_table.update(
            increment_num_agreements, 
            doc_ids=[0]
        )

        self.logger.info(entry)
        

    # adds a ruling vote to the agreement from the member or creator
    def vote(self, account, ruling):
        entry = self.get_entry()

        # adds ruling if member
        if str(account.id) == entry['member_id']:
            self.agreement_table.update(
                {'member_ruling': ruling},
                doc_ids=[self.id]
            )
            self.logger.info(f'Member {account.screen_name} [{account.id}] voted {ruling} on Agreement #{self.id}')

        # adds ruling if creator
        elif str(account.id) == entry['creator_id']:
            self.agreement_table.update(
                {'creator_ruling': ruling},
                doc_ids=[self.id]
            )
            self.logger.info(f'Creator {account.screen_name} [{account.id}] voted {ruling} on Agreement #{self.id}')

        # extracting from db
        collateral_type = entry['collateral_type']
        collateral = int(entry['collateral'])
        member_id = int(entry['member_id'])
        member_screen_name = entry['member_screen_name']
        creator_id = int(entry['creator_id'])
        creator_screen_name = entry['creator_screen_name']

        # checks the current ruling state of the agreement
        ruling = self.check_ruling()

        # both users say the agreement was upheld
        if ruling == 'upheld':
            # if the creator used xsc as collateral, it is returned to their balance
            if collateral_type == 'xsc':
                account.change_balance(creator_id, collateral)
                self.logger.info(f'Paid back {collateral} XSC to {creator_screen_name} [{creator_id}] ')

                update_message = f'Agreement is upheld, {collateral} XSC has been repaid to @{creator_screen_name}.'
            # if the creator used likes/retweets as collateral nothing happens and the contracts aren't generated
            else:
                self.logger.info(f'Collateral type was future contract, nothing to do')
                # effectively zeroes out dead contract
                core.db.table('contracts').update(
                    {'count': '0'},
                    doc_ids=[self.id]
                )
                
                update_message = f'Agreement is upheld, no contracts will be generated.'


        # both users say the agreement was broken
        elif ruling == 'broken':
            # if the creator used xsc as collateral, it is transferred to the member
            if collateral_type == 'xsc':
                account.change_balance(member_id, collateral)
                self.logger.info(f'Transferred {collateral} XSC to {member_id} [{member_id}]')
                update_message = f'Agreement is broken, {collateral} XSC has been paid to @{member_screen_name}'
            # if the creator used likes/retweets as collateral, a contract is generated and the profit is transferred to the member
            elif (collateral_type == "like") or (collateral_type == "retweet"):
                # retrieving inactive contract
                c_entry = core.db.table('contracts').get(doc_id=self.id)
                c_total = int(c_entry['count'])
                c_value = int(c_entry['price'])
                total_value = c_total * c_value

                # paying tax to agreement engine
                to_pay_engine = math.ceil(total_value * core.Consts.tax_rate)
                collateral = total_value - to_pay_engine

                core.db.table('contracts').update(
                    {'state': 'alive'},
                    doc_ids=[self.id]
                )    
                self.logger.info(f'Collateral contract #{self.id} activated')

                # paid out to agreement engine
                account.change_balance(core.engine_id, to_pay_engine)
                account.change_balance(member_id, collateral)
                self.logger.info(f'Transferred {collateral} XSC to {member_screen_name} [{member_id}]') 
                update_message = f'Agreement is broken, @{creator_screen_name}\'s contract was generated and {collateral} XSC has been paid to @{member_screen_name}.'
                
        elif ruling == 'disputed':
            update_message = f'Agreement outcome is disputed. No action will be taken, users can change their ruling to come to a consensus.'

        if (ruling == 'upheld') or (ruling == 'broken') or (ruling == 'disputed'):
            if core.Consts.send_tweets:
                # post to twitter
                core.api.update_status(
                    status = update_message + " #" + str(self.id), 
                    in_reply_to_status_id = self.id, 
                    auto_populate_reply_metadata= True)
            else:
                print(update_message + " #" + str(self.id))
                       

    
    def check_ruling(self):
        m_ruling = self.get_entry()['member_ruling']
        c_ruling = self.get_entry()['creator_ruling']

        if m_ruling and c_ruling:
            if m_ruling == c_ruling:
                self.logger.info(f'Consensus reached: {c_ruling}')
                return c_ruling
            else:
                self.logger.info('Dispute in agreement')
                return 'disputed'
        else:
            self.logger.info('Have not received all rulings')
            return 'waiting'