import metagov.core.plugin_decorators as Registry
import requests
from metagov.core.errors import PluginErrorInternal
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
        return {"value": cred}

    def get_user_cred(self, username):
        server = self.config["server_url"]
        resp = requests.get(f"{server}/output/accounts.json")
        if resp.status_code == 404:
            raise PluginErrorInternal(
                "'output/accounts.json' file not present. Run 'yarn sourcecred analysis' when generating sourcecred instance."
            )
        if resp.status_code == 200:
            cred_data = resp.json()
            for account in cred_data["accounts"]:
                name = account["account"]["identity"]["name"]
                if name == username:
                    return account["totalCred"]
            raise PluginErrorInternal(f"{username} not found in sourcecred instance")

        raise PluginErrorInternal(f"Error {resp.status_code} {resp.reason}")
