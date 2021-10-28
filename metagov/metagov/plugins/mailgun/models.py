from metagov.core.plugin_manager import AuthorizationType, Registry, Parameters, VotingStandard
from metagov.core.models import Plugin

import requests

@Registry.plugin
class Mailgun(Plugin):
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
    def send_message(self, **kwargs):
        # making post request to mailgun api
        response = requests.post(
            url='https://api.mailgun.net/v3/{0}/messages'.format(self.config['domain_name']),
            auth=('api', self.config['api_key']),
            data=kwargs # this is the json set in internal/action/mailgun.send-mail
        )

        return response.json()