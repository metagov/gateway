import metagov.core.plugin_decorators as Registry
from metagov.core.models import Plugin

import requests

@Registry.plugin
class TSC(Plugin):
    name = "tsc"
    config_schema = {
        "type": "object",
        "properties": {
            "server_url": {"type": "string"}
        },
        "required": ["server_url"]
    }

    class Meta:
        proxy = True

    @Registry.action(
        slug="get-user",
        description="Returns information about a requested user",
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"}
            },
            "required": ["user_id"]
        },
        output_schema={
            "type": "object",
            "properties": {
                "balance": {"type": "string"},
                # "contracts": {"type": "list"}
            }
        }
    )
    def get_user(self, data):
        url = self.config['server_url'] + '/api/user/' + data['user_id']
        response = requests.get(url)

        return response.json()
