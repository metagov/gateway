import logging
from django.conf import settings
from metagov.core.models import Plugin
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from metagov.core.plugin_manager import Registry
from metagov.core.errors import PluginErrorInternal

sendgrid_settings = settings.METAGOV_SETTINGS["SENDGRID"]
SENDGRID_API_KEY = sendgrid_settings["API_KEY"]

logger = logging.getLogger(__name__)

@Registry.plugin
class SendGrid(Plugin):
    name = 'sendgrid'

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
            logger.info(response.status_code, response.body)
            if response.status_code != 202:
                raise PluginErrorInternal("There was error sending email")
        except Exception as e:
            logger.error(e.message)
            raise PluginErrorInternal("There was error sending email")
