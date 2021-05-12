import logging

import metagov.core.plugin_decorators as Registry
import metagov.plugins.near.schemas as Schemas
import near_api
from metagov.core.errors import PluginErrorInternal
from metagov.core.models import Plugin
from near_api.account import TransactionError, ViewFunctionError

logger = logging.getLogger(__name__)

"""
**** HOW TO USE: SputnikDAO example ***


# Deploy a contract
near dev-deploy res/sputnikdao.wasm
CONTRACT_ID=dev-X # account id

# Initialize the contract
near call $CONTRACT_ID new '{"purpose": "testing metagov", "council": ["dev.mashton.testnet"], "bond": "100", "vote_period": "1800000000000", "grace_period": "1800000000000"}' --accountId $CONTRACT_ID

# Generate a key or use the default one
# Find the private_key here:
PRIVATE_KEY=$(cat ~/.near-credentials/default/$CONTRACT_ID.json | jq .private_key)


Enable the plugin for a test community:

curl -X PUT 'http://127.0.0.1:8000/api/internal/community/my-community-123' \
    -H 'Content-Type: application/json' \
    --data-raw '{
        "name": "my-community-123",
        "readable_name": "my test community",
        "plugins": [
            {
                "name": "near",
                "config": {
                    "contract_id": $CONTRACT_ID,
                    "account_id": $CONTRACT_ID,
                    "secret_key": $PRIVATE_KEY,
                    "node_url": "https://rpc.testnet.near.org"
                }
            }
        ]
    }'


Make a NEAR function call:

curl -X POST 'http://127.0.0.1:8000/api/internal/action/near.call' \
    -H 'Content-Type: application/json' \
    -H 'X-Metagov-Community: my-community-123' \
    --data-raw '{
        "parameters": {
            "method_name": "add_proposal",
            "args": {
                "proposal": {
                    "description": "pay me",
                    "kind": {"type": "Payout",  "amount": "100" },
                    "target": "dev.mashton.testnet"
                }
            },
            "gas": 100000000000000,
            "amount": 100000000000000
        }
    }'
"""

@Registry.plugin
class Near(Plugin):
    name = "near"
    config_schema = {
        "type": "object",
        "properties": {
            "contract_id": {"type": "string"},
            "account_id": {"type": "string"},
            "secret_key": {"type": "string"},
            "node_url": {"type": "string", "default": "https://rpc.testnet.near.org"},
        },
        "required": ["contract_id", "account_id", "secret_key", "node_url"],
    }

    class Meta:
        proxy = True

    def initialize(self):
        logger.info(f"NEAR: Initialized plugin for contract {self.config['contract_id']}")
        logger.info(f"NEAR: This instance belongs to community: {self.community}")

        # create Signer and serialize it in state. we only need to create it once.
        signer = near_api.signer.Signer(
            self.config["account_id"],
            near_api.signer.KeyPair(
                self.config["secret_key"],
            ),
        )
        self.state.set("signer", signer)

    def create_master_account(self):
        # Create RPC provider
        provider = near_api.providers.JsonProvider(self.config["node_url"])

        account_id = self.config["account_id"]
        signer = self.state.get("signer")  # deserialize signer
        account = near_api.account.Account(provider, signer, account_id)
        return account

    @Registry.action(
        slug="view",
        description="Makes a contract call which can only view state.",
        input_schema=Schemas.view_parameters,
    )
    def view(self, parameters):
        contract_id = self.config["contract_id"]
        method_name = parameters["method_name"]
        args = parameters.get("args", {})

        account = self.create_master_account()  # creates a new provider every time!

        try:
            return account.view_function(contract_id, method_name, args)
        except (TransactionError, ViewFunctionError) as e:
            raise PluginErrorInternal(str(e))

    @Registry.action(
        slug="call",
        description="Makes a contract call which can modify or view state.",
        input_schema=Schemas.call_parameters,
    )
    def call(self, parameters):
        """
        'Contract calls require a transaction fee (gas) so you will need an
        access key for the --accountId that will be charged. (near login)'

        In this case we only support making calls from the "master account"...
        """
        contract_id = self.config["contract_id"]

        account = self.create_master_account()  # creates a new provider every time!

        optional_args = {key: parameters[key] for key in parameters.keys() if key in ["gas", "amount"]}
        try:
            return account.function_call(
                contract_id=contract_id,
                method_name=parameters["method_name"],
                args=parameters.get("args", {}),
                **optional_args,
            )
        except (TransactionError, ViewFunctionError) as e:
            raise PluginErrorInternal(str(e))
