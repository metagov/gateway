import json

import metagov.core.plugin_decorators as Registry
import requests
from metagov.core.models import Plugin


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
        if cred is None:
            raise Exception(f"{username} not found in sourcecred instance")
        return {"value": cred}

    def get_user_cred(self, username):
        server = self.config["server_url"]
        url = f"{server}/output/accounts.json"
        resp = requests.get(url)
        cred_data = resp.json()
        for account in cred_data["accounts"]:
            name = account["account"]["identity"]["name"]
            if name == username:
                return account["totalCred"]
        return None
