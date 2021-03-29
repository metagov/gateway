import json
import requests
import metagov.core.plugin_decorators as Registry
from metagov.core.models import Plugin


input_schema = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "username": {"description": "Username on the platform used with this sourcecred instance", "type": "string"}
    },
    "required": ["username"],
}

output_schema = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"value": {"description": "Users most recent Cred value", "type": "number"}},
}


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

    @Registry.resource(
        slug="cred", description="Cred value for given user", input_schema=input_schema, output_schema=output_schema
    )
    def get_cred(self, parameters):
        username = parameters["username"]
        cred = self.get_user_cred(username)
        if cred is None:
            # can we specify Not Found?
            raise Exception(f"{username} not found in sourcecred instance")
        return {"value": cred}

    @Registry.action(
        slug="getcred", description="Cred value for given user", input_schema=input_schema, output_schema=output_schema
    )
    def cred_as_an_action(self, parameters, user_id):
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
