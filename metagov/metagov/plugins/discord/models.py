import json
import logging

import requests
from django.conf import settings
from metagov.core.errors import PluginErrorInternal
from metagov.core.models import AuthType, Plugin, ProcessStatus, GovernanceProcess
from metagov.core.plugin_manager import Registry, Parameters

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
        logger.debug(f"{self} received event {t} {name}:")
        logger.debug(json_data)
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
    def post_message(self, text, channel, **kwargs):
        kwargs["content"] = text
        return self._make_discord_request(f"/channels/{channel}/messages", "POST", json=kwargs)


VOTE_ACTION_ID = "cast_vote"


class Bool:
    YES = "yes"
    NO = "no"


class Type:
    ACTION_ROW = 1
    BUTTON = 2


@Registry.governance_process
class DiscordVote(GovernanceProcess):
    name = "vote"
    plugin_name = "discord"

    class Meta:
        proxy = True

    def start(self, parameters: Parameters) -> None:
        poll_type = parameters.poll_type
        options = [Bool.YES, Bool.NO] if poll_type == "boolean" else parameters.options
        if options is None:
            raise PluginErrorInternal("Options are required for non-boolean votes")

        # maybe_channel = parameters.channel
        # maybe_users = parameters.eligible_voters
        # if maybe_channel is None and (maybe_users is None or len(maybe_users) == 0):
        #     raise PluginErrorInternal("eligible_voters or channel are required")

        self.state.set("poll_type", poll_type)
        self.state.set("options", options)
        self.outcome = {
            "votes": dict([(k, {"users": [], "count": 0}) for k in options]),
        }

        components = self._construct_blocks()
        logger.debug(components)
        resp = self.plugin_inst.post_message(text=parameters.title, components=components, channel=parameters.channel)
        logger.debug(resp)
        # self.outcome["url"] = permalink_resp["permalink"]
        # self.outcome["channel"] = channel
        # self.outcome["message_ts"] = ts
        self.status = ProcessStatus.PENDING.value
        self.save()

    def _construct_blocks(self, hide_buttons=False):
        """
        Construct voting message blocks
        """
        poll_type = self.state.get("poll_type")
        options = self.state.get("options")
        votes = self.outcome["votes"]

        blocks = []
        for idx, opt in enumerate(options):
            if poll_type == "boolean":
                option_text = f"Approve" if opt == Bool.YES else "Reject"
                button_emoji = "👍" if opt == Bool.YES else "👎"
            else:
                option_text = opt
                button_emoji = None

            # show vote count and user list next to each vote option
            num = votes[opt]["count"]
            option_text = f"{option_text}   `{num}`"
            if num > 0:
                users = [f"<@{id}>" for id in votes[opt]["users"]]
                users = ", ".join(users)
                option_text = f"{option_text} ({users})"

            if not hide_buttons:
                button = {
                    "type": Type.BUTTON,
                    "label": option_text,
                    "style": 1,
                    "custom_id": f"{VOTE_ACTION_ID}_{opt}",
                }
                if button_emoji:
                    button["emoji"] = {"name": button_emoji}
                blocks.append(button)

        return [{"type": 1, "components": blocks}]

    def receive_webhook(self, request):
        logger.debug(f"{self} processing interaction {request}")
        pass

    def close(self):
        # Set governnace process to completed
        self.status = ProcessStatus.COMPLETED.value
        # Update vote message to hide voting buttons
        self.save()