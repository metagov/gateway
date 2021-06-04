import metagov.core.plugin_decorators as Registry
from metagov.core.models import Plugin

import requests

@Registry.plugin
class Tutorial(Plugin):
    name = 'mailgun'
    config_schema = {
        "type": "object",
        "properties": {
            "domain_name": {"type": "string"},
            "api_key": {"type": "string"}
        },
        "required": ["domain_name", "api_key"]
    }

    class Meta:
        proxy = True

    @Registry.action(
        slug="send-mail",
        description="Sends an email",
        input_schema={
            "type": "object",
            "properties": {
                "from": {
                    "description": "Address email being sent from",
                    "type": "string"
                },
                "to": {
                    "description": "Address email being sent to",
                    "type": "string"
                },
                "subject": {
                    "description": "Subject of the email",
                    "type": "string"
                },
                "text": {
                    "description": "Text of the email body",
                    "type": "string"
                }
            },
            "required": ["from", "to", "text"]
        },
        output_schema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string"
                },
                "message": {
                    "type": "string"
                }
            }
        }
    )
    def send_message(self, data):
        response = requests.post(
            url='https://api.mailgun.net/v3/{0}/messages'.format(self.config['domain_name']),
            auth=('api', self.config['api_key']),
            data=data
        )

        return response.json()