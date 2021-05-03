import logging
import time
from datetime import datetime, timedelta, timezone

import metagov.core.plugin_decorators as Registry
import metagov.plugins.near.schemas as Schemas
import near_api
from metagov.core.models import GovernanceProcess, Plugin, ProcessStatus

logger = logging.getLogger(__name__)


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

        result = account.view_function(contract_id, method_name, args)
        return result

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
        result = account.function_call(
            contract_id=contract_id,
            method_name=parameters["method_name"],
            args=parameters.get("args", {}),
            **optional_args,
        )
        return result
