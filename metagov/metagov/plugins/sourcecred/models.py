import logging
from typing import Dict, Optional

from metagov.core.plugin_manager import AuthorizationType, Registry, Parameters, VotingStandard
import requests
from metagov.core.errors import PluginErrorInternal
from metagov.core.models import Plugin

logger = logging.getLogger(__name__)


@Registry.plugin
class SourceCred(Plugin):
    name = "sourcecred"
    config_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"server_url": {"description": "URL of the SourceCred server", "type": "string"}},
        "required": ["server_url"],
    }

    class Meta:
        proxy = True

    @Registry.action(
        slug="user-cred",
        description="Get most recent cred value for given user",
        input_schema={
            "type": "object",
            "properties": {
                "username": {
                    "description": "Username on the platform used with this sourcecred instance",
                    "type": "string",
                },
                "id": {
                    "description": "The id of any account on the platform used with this sourcecred instance",
                    "type": "string",
                },
            },
        },
        output_schema={"type": "object", "properties": {
            "value": {"type": "number"}}},
        is_public=True,
    )
    def get_cred(self, parameters):
        username = parameters.get('username')
        id = parameters.get('id')
        cred = self.get_user_cred(username=username, id=id)
        return {"value": cred}

    @Registry.action(
        slug="total-cred",
        description="Get total cred for the community",
        output_schema={"type": "object", "properties": {
            "value": {"type": "number"}}},
        is_public=True,
    )
    def fetch_total_cred(self, parameters):
        cred_data = self.fetch_accounts_analysis()
        total = 0
        for account in cred_data["accounts"]:
            total += account["totalCred"]
        return {"value": total}

    def get_user_cred(self, username: Optional[str] = None, id: Optional[str] = None):
        cred_data = self.fetch_accounts_analysis()
        if not (username or id):
            raise PluginErrorInternal(
                "Either a username or an id argument is required")
        for account in cred_data["accounts"]:
            name = account["account"]["identity"]["name"]
            """
            Account aliases is how sourcecred stores internal ids of accounts for
            all platforms, storing the id in a format like this 
            "N\u0000sourcecred\u0000discord\u0000MEMBER\u0000user\u0000140750062325202944\u0000"
            the discord id for example is store in the index before last always
            the same could apply to discourse, github, and whatever 
            """
            account_aliases: list = account['account']["identity"]["aliases"]
            if id:
                # Making sure the id is in string form for comparison
                id = str(id)
                for alias in account_aliases:
                    alias_id = alias["address"].split("\u0000")[-2]
                    if alias_id == id:
                        return account["totalCred"]
            if username and name == username:
                return account["totalCred"]
        raise PluginErrorInternal(
            f"{username or id} not found in sourcecred instance")

    def fetch_accounts_analysis(self):
        server = self.config["server_url"]
        resp = requests.get(f"{server}/output/accounts.json")
        if resp.status_code == 404:
            raise PluginErrorInternal(
                "'output/accounts.json' file not present. Run 'yarn sourcecred analysis' when generating sourcecred instance."
            )
        if resp.status_code == 200:
            accounts = resp.json()
            return accounts

        raise PluginErrorInternal(
            f"Error fetching SourceCred accounts.json: {resp.status_code} {resp.reason}")
