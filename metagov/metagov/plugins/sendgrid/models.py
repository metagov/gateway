from django.conf import settings
from metagov.core.models import Plugin
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from metagov.core.plugin_manager import Registry

sendgrid_settings = settings.METAGOV_SETTINGS["SENDGRID"]
SENDGRID_API_KEY = sendgrid_settings["SENDGRID_API_KEY"]


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
                "from_email": {
                    "description": "Address email being sent from",
                    "type": "string"
                },
                "to_emails": {
                    "description": "Address email being sent to",
                    "type": "string"
                },
                "subject": {
                    "description": "Subject of the email",
                    "type": "string"
                },
                "html_content": {
                    "description": "Text of the email body in HTML format",
                    "type": "string"
                }
            },
            "required": ["from", "to", "subject", "html_content"]
        },
        output_schema={
            "type": "object",
            "properties": {
                "response": {
                    "type": "boolean"
                },
            }
        }
    )
    def send_message(self, **kwargs):
        """
            kwargs_struct = {
                "to_emails": "to@example.com",
                "from_email": "from_email@example.com",
                "subject": "Sending with Twilio SendGrid is Fun",
                "html_content": "<strong>and easy to do anywhere, even with Python</strong>"
                }
        """
        message = Mail(**kwargs)
        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)
            print(response.status_code, response.body)
            return True
        except Exception as e:
            print(e.message)
            return False
