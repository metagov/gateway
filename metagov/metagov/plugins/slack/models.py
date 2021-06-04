import json
import logging

import metagov.core.plugin_decorators as Registry
import requests
from metagov.core.errors import PluginErrorInternal
from metagov.core.models import Plugin

logger = logging.getLogger(__name__)

"""

App Manifest
https://app.slack.com/app-settings/TMQ3PKXT9/A01HT9U26NT/app-manifest

1. Upload the App Manifest
2. Copy the Client ID/Secret/etc onto the server
"""


@Registry.plugin
class Slack(Plugin):
    name = "slack"
    config_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            # these are set automatically if using the oauth flow
            "team_id": {"description": "Slack Team ID", "type": "string"},
            "team_name": {"description": "Slack Team Name", "type": "string"},
            "bot_token": {"description": "Bot Token", "type": "string"},
            "bot_user_id": {"description": "Bot User ID", "type": "string"},
        },
    }

    class Meta:
        proxy = True

    def initialize(self):
        logger.info(f"Initializing Slack Plugin for {self.community}")
        logger.info(self.config["team_name"])

    @Registry.webhook_receiver(event_schemas=[])
    def receive_event(self, request):
        """
        Passes on ALL received events to the driver
        """
        json_data = json.loads(request.body)
        if json_data["type"] != "event_callback" or json_data["team_id"] != self.config["team_id"]:
            return

        # Datat types: https://api.slack.com/apis/connections/events-api#the-events-api__receiving-events__events-dispatched-as-json
        # Event list: https://api.slack.com/events

        event = json_data["event"]

        # pop off 'type' and 'user' since they are represented separately in metagov-style event
        event_type = event.pop("type")
        maybe_user = event.pop("user", None)

        logger.info(f"Received event {event_type}")

        initiator = {
            "user_id": maybe_user,
            "provider": "slack",
            "is_metagov_bot": maybe_user and maybe_user == self.config["bot_user_id"],
        }
        self.send_event_to_driver(event_type=event_type, initiator=initiator, data=event)

    @Registry.action(
        slug="method",
        input_schema={
            "type": "object",
            "properties": {"method_name": {"type": "string"}},
            "required": ["method_name"],
        },
        description="Perform any Slack method (provided sufficient scopes)",
    )
    def method(self, parameters):
        """
        Action for performing any method in https://api.slack.com/methods
        See also: https://api.slack.com/web#basics

        Example usage:

        curl -iX POST "https://prototype.metagov.org/api/internal/action/slack.method" -H  "accept: application/json" -H  "X-Metagov-Community: slack-tmq3pkxt9" -d '{"parameters":{"method_name":"chat.postMessage", "channel":"C0177HZTV7X", "text":"hello world"}}'
        curl -iX POST "https://prototype.metagov.org/api/internal/action/slack.method" -H  "accept: application/json" -H  "X-Metagov-Community: slack-tmq3pkxt9" -d '{"parameters":{"channel":"C0177HZTV7X","method":"pins.add","timestamp":"1622820212.008000"}}'
        curl -iX POST "https://prototype.metagov.org/api/internal/action/slack.method" -H  "accept: application/json" -H  "X-Metagov-Community: slack-tmq3pkxt9" -d '{"parameters":{"channel":"C0177HZTV7X","method":"pins.remove","timestamp":"1622820212.008000"}}'
        """
        method = parameters.pop("method_name")
        data = {"token": self.config["bot_token"], **parameters}
        return self.slack_request("POST", method, data=data)

    def slack_request(self, method, route, json=None, data=None):
        url = f"https://slack.com/api/{route}"
        logger.info(f"{method} {url}")
        resp = requests.request(method, url, json=json, data=data)
        if not resp.ok:
            logger.error(f"{resp.status_code} {resp.reason}")
            logger.error(resp.request.body)
            raise PluginErrorInternal(resp.text)
        if resp.content:
            data = resp.json()
            is_ok = data.pop("ok")
            if not is_ok:
                raise PluginErrorInternal(data["error"])
            return data
        return {}
