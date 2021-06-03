import logging

import metagov.core.plugin_decorators as Registry
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
                }
            },
            "required": ["username"],
        },
        output_schema={"type": "object", "properties": {"value": {"type": "number"}}},
        is_public=True,
    )
    def get_cred(self, parameters):
        username = parameters["username"]
        cred = self.get_user_cred(username)
        return {"value": cred}

    @Registry.action(
        slug="total-cred",
        description="Get total cred for the community",
        output_schema={"type": "object", "properties": {"value": {"type": "number"}}},
        is_public=True,
    )
    def fetch_total_cred(self, parameters):
        cred_data = self.fetch_accounts_analysis()
        total = 0
        for account in cred_data["accounts"]:
            total += account["totalCred"]
        return {"value": total}

    def get_user_cred(self, username):
        cred_data = self.fetch_accounts_analysis()
        for account in cred_data["accounts"]:
            name = account["account"]["identity"]["name"]
            if name == username:
                return account["totalCred"]
        raise PluginErrorInternal(f"{username} not found in sourcecred instance")

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

        raise PluginErrorInternal(f"Error fetching SourceCred accounts.json: {resp.status_code} {resp.reason}")
