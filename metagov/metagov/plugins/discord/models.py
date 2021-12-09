import json
import logging

import requests
from django.conf import settings
from metagov.core.errors import PluginErrorInternal
from metagov.core.models import AuthType, GovernanceProcess, Plugin, ProcessStatus
from metagov.core.plugin_manager import Registry

logger = logging.getLogger(__name__)

discord_settings = settings.METAGOV_SETTINGS["DISCORD"]
DISCORD_BOT_TOKEN = discord_settings["BOT_TOKEN"]


@Registry.plugin
class Discord(Plugin):
    name = "discord"
    auth_type = AuthType.OAUTH
    config_schema = {
        "type": "object",
        "properties": {
            # these are set automatically using the oauth flow
            "guild_id": {"description": "Discord Guild ID", "type": "number"},
            "guild_name": {"description": "Discord Guild Name", "type": "string"},
        },
    }
    community_platform_id_key = "guild_id"

    class Meta:
        proxy = True

    # def initialize(self):
    #     logger.debug(f"init discord {self.config}")
    #     guild_id = self.config["guild_id"]
    #     guild = self._make_discord_request(f"/guilds/{guild_id}")
    #     self.state.set("guild_data", guild)

    def receive_event(self, request):
        json_data = json.loads(request.body)
        t = json_data["type"]
        name = json_data["name"]
        logger.debug(f">> {self} got event {t} {name}")
        logger.debug(json_data)
        logger.debug("--")
        user = json_data.get("user")

        # initiator = {
        #     "user_id": message["author"]["name"],
        #     "provider": "discord",
        #     "is_metagov_bot": message["author"]["bot"],
        # }
        # self.send_event_to_driver(event_type=name, initiator=initiator, data=json_data)

    def _make_discord_request(self, route, method="GET", json=None):
        if not route.startswith("/"):
            route = f"/{route}"

        resp = requests.request(
            method,
            f"https://discord.com/api{route}",
            headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
            json=json,
        )

        if not resp.ok:
            logger.error(f"{resp.status_code} {resp.reason}")
            logger.debug(resp.request.headers)
            logger.debug(resp.request.url)
            raise PluginErrorInternal(resp.text)
        if resp.content:
            return resp.json()
        return None

    @Registry.action(
        slug="method",
        input_schema={
            "type": "object",
            "properties": {
                "method": {"type": "string", "description": "HTTP method. Defaults to GET."},
                "route": {"type": "string"},
            },
            "required": ["route"],
        },
        description="Perform any Discord API call",
    )
    def method(self, route, method="GET", **kwargs):
        return self._make_discord_request(route, method, json=kwargs)

    @Registry.action(
        slug="get-guild",
        description="Get guild information",
    )
    def get_guild(self):
        guild_id = self.config["guild_id"]
        return self._make_discord_request(f"/guilds/{guild_id}")

    @Registry.action(
        slug="post-message",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}, "channel": {"type": "number"}},
            "required": ["text", "channel"],
        },
        description="Post message in a channel.",
    )
    def post_message(self, text, channel, users, **kwargs):
        kwargs["content"] = text
        return self._make_discord_request(f"/channels/{channel}/messages", "POST", json=kwargs)
