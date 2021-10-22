import environ
import json
import logging
import requests

from metagov.core.models import GovernanceProcess, Plugin, ProcessStatus, AuthType
from metagov.core.plugin_manager import Registry, Parameters, VotingStandard
from rest_framework.exceptions import ValidationError
from metagov.core.errors import PluginErrorInternal

logger = logging.getLogger(__name__)

env = environ.Env()
environ.Env.read_env()
DISCORD_BOT_TOKEN = env("DISCORD_BOT_TOKEN")


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

    class Meta:
        proxy = True

    # def initialize(self):
    #     logger.debug(f"init discord {self.config}")
        # guild_id = self.config["guild_id"]
        # guild = self._make_discord_request(f"/guilds/{guild_id}")
        # self.state.set("guild_data", guild)
        # ... create webhook for guild / channel ?

    def receive_event(self, request):
        json_data = json.loads(request.body)
        t = json_data["type"]
        name = json_data["name"]
        logger.debug(f">> {self} got event {t} {name}")
        user = json_data.get("user")

    #     initiator = {
    #         "user_id": message["author"]["name"],
    #         "provider": "discord",
    #         "is_metagov_bot": message["author"]["bot"],
    #     }
    #     self.send_event_to_driver(event_type=event_type, initiator=initiator, data=message)

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
    def discord_method(self, parameters):
        method = parameters.pop("method", "GET")
        route = parameters.pop("route")
        # TODO fill in guild id
        return self._make_discord_request(route, method, json=parameters)

    """
    @Registry.action(
        slug="getuser",
        input_schema={
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
            "required": ["user_id"],
        },
        description="Returns a user with the given ID or None if not found.",
    )
    def getuser(self, parameters):
        user_id = parameters.pop("user_id")
        return self.client.get_user(user_id)

    """

    @Registry.action(
        slug="get-guild",
        description="Get guild information",
    )
    def get_guild(self, parameters):
        guild_id = self.config["guild_id"]
        return self._make_discord_request(f"/guilds/{guild_id}")

    """
    @Registry.action(
        slug="post-message",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}, "channel": {"type": "number"}, "user": {"type": "number"}},
            "required": ["text"],
        },
        description="Post message either in a channel or direct message.",
    )
    def post_message(self, parameters):
        if not parameters.get("channel") and not parameters.get("user"):
            raise ValidationError("channel or user is required")
        if parameters.get("channel"): # Post message to channel
            channel = self.client.get_channel(parameters.get("channel"))
            if channel.type != discord.ChannelType.text:
                raise ValidationError("channel passed in must be a TextChannel")
            channel.send(parameters.get("text"))
        else: # Post message to direct message
            user = self.client.get_user(parameters.get("user"))
            user.send(parameters.get("text"))

    @Registry.action(
        slug="post-reply",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}, "channel": {"type": "number"}, "message": {"type": "number"}},
            "required": ["text", "channel", "message"],
        },
        description="Post reply to a message.",
    )
    def post_reply(self, parameters):
        channel = self.client.get_channel(parameters.get("channel"))
        if channel.type != discord.ChannelType.text:
            raise ValidationError("channel passed in must be a TextChannel")
        message = channel.get_partial_message(parameters.get("text"))
        message.reply(content=parameters.get("reply"))

    @Registry.action(
        slug="create-channel",
        input_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}, "type": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["name", "type"],
        },
        description="Create a text, voice or stage channel.",
    )
    def create_channel(self, parameters):
        guild = self.client.get_guild(self.config["guild_id"])
        if type == "text":
            guild.create_text_channel(parameters.get("name"), reason=parameters.get("reason"))
        elif type == "voice":
            guild.create_voice_channel(parameters.get("name"), reason=parameters.get("reason"))
        elif type == "stage":
            guild.create_stage_channel(parameters.get("name"), reason=parameters.get("reason"))
        else:
            raise ValidationError("type passed in must be 'text', 'voice' or 'stage'")

    @Registry.action(
        slug="delete-channel",
        input_schema={
            "type": "object",
            "properties": {"channel": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["channel"],
        },
        description="Delete a channnel.",
    )
    def delete_channel(self, parameters):
        channel = self.client.get_channel(parameters.get("channel"))
        channel.delete(reason=parameters.get("reason"))

    def get_user(self, user_id):
        guild = self.client.get_guild(self.config["guild_id"])
        return guild.get_member(user_id)

    @Registry.action(
        slug="kick-user",
        input_schema={
            "type": "object",
            "properties": {"user": {"type": "number"}},
            "required": ["user"],
        },
        description="Kick a user from the guild.",
    )
    def kick_user(self, parameters):
        user = self.get_user(parameters.get("user"))
        user.kick()

    @Registry.action(
        slug="ban-user",
        input_schema={
            "type": "object",
            "properties": {"user": {"type": "number"}},
            "required": ["user"],
        },
        description="Ban a user from the guild.",
    )
    def ban_user(self, parameters):
        user = self.get_user(parameters.get("user"))
        user.ban()

    @Registry.action(
        slug="unban-user",
        input_schema={
            "type": "object",
            "properties": {"user": {"type": "number"}},
            "required": ["user"],
        },
        description="Unban a user from the guild.",
    )
    def unban_user(self, parameters):
        user = self.get_user(parameters.get("user"))
        user.unban()
    """