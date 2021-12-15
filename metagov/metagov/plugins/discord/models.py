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
CLIENT_ID = discord_settings["CLIENT_ID"]

SLASH_COMMAND_EVENT_TYPE = "slash_command"


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

    def initialize(self):
        logger.debug(f"Initializing Discord with config: {self.config}")

    #     guild_id = self.config["guild_id"]
    #     guild = self._make_discord_request(f"/guilds/{guild_id}")
    #     self.state.set("guild_data", guild)

    def receive_event(self, request):
        """
        Receive interaction request from Discord for this guild. Only supports slash commands for now.

        Example payload for slash command "/policykit command: 'hello world'"

            {'application_id': '0000000',
            'channel_id': '0000000',
            'data': {
                'id': '0000000',
                'name': 'policykit',
                'options': [
                    {'name': 'command', 'type': 3, 'value': 'hello world'}
                ],
                'type': 1
            },
            'guild_id': '0000000',
            'id': '0000000',
            'member': {
                'avatar': None,
                'communication_disabled_until': None,
                'deaf': False,
                'is_pending': False,
                'joined_at': '2020-11-25T18:41:50.890000+00:00',
                'mute': False,
                'nick': None,
                'pending': False,
                'permissions': '0000000',
                'premium_since': None,
                'roles': [],
                'user': {'avatar': None,
                'discriminator': '0000000',
                'id': '0000000',
                'public_flags': 0,
                'username': 'miri'}
            },
            'token': 'REDACTED',
            'type': 2,
            'version': 1}
        """
        interaction_object = json.loads(request.body)
        if interaction_object["type"] != 2:
            # ignore it if its not an application command
            return None
        if interaction_object["data"]["type"] != 1:
            # ignore it if its not a slash command
            # https://discord.com/developers/docs/interactions/application-commands#application-command-object-application-command-types
            return None

        command = interaction_object["data"]["name"]
        user_id = interaction_object["member"]["user"]["id"]
        username = interaction_object["member"]["user"]["username"]
        logger.debug(f"Received slash command '{command}' from {username}")

        initiator = {"user_id": user_id, "provider": "discord", "is_metagov_bot": False}

        # Send the whole interaction object to the driver
        self.send_event_to_driver(event_type=SLASH_COMMAND_EVENT_TYPE, initiator=initiator, data=interaction_object)

        # Respond to the interaction
        # See: https://discord.com/developers/docs/interactions/receiving-and-responding#responding-to-an-interaction

        # return {"type": 5}  # ACK an interaction and edit a response later, the user sees a loading state
        return {"type": 4, "data": {"content": "Message received!", "flags": 1 << 6}}

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
        slug="register-guild-command",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "command_id": {
                    "type": "string",
                    "description": "required if updating an existing command",
                },
                # any other args are passed along to discord commands endpoing
            },
            "required": ["name"],
        },
        description="Register or update a command for this guild.",
    )
    def register_guild_command(self, name, description=None, command_id=None, **kwargs):
        """
        Register or update a guild-specific command.
        See https://discord.com/developers/docs/interactions/application-commands#registering-a-command
        """
        json = {
            "name": name,
            "description": description,
            **kwargs
            # "options": [{"name": "command", "description": "Command", "type": 3}],
        }
        route = f"/v8/applications/{CLIENT_ID}/guilds/{self.config['guild_id']}/commands"
        if command_id:
            route = f"{route}/{command_id}"
        response = self._make_discord_request(route=route, method="POST", json=json)
        logger.debug(response)
        return response

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
        return self._make_discord_request(route, method, json=kwargs if kwargs else None)

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

    @Registry.action(
        slug="interaction-message",
        input_schema={
            "type": "object",
            "properties": {
                "interaction_token": {"type": "string"},
                "edit_original": {"type": "boolean", "description": "whether to edit the original message"},
                "delete_original": {"type": "boolean", "description": "whether to delete the original message"},
                "message_id": {
                    "type": "number",
                    "description": "if provided, update this message id. must be a message that was sent with the interaction token.",
                },
            },
            "required": ["interaction_token"],
        },
        description="Respond to an interaction. Requires an interaction token, which is only valid for 15 minutes after the interaction.",
    )
    def interaction_message(
        self, interaction_token, delete_original=False, edit_original=False, message_id=None, **kwargs
    ):
        """
        Respond to an interaction. Requires an interaction token, which is only valid for 15 minutes after the interaction.

        See: https://discord.com/developers/docs/interactions/receiving-and-responding#followup-messages
        """
        url = f"/webhooks/{CLIENT_ID}/{interaction_token}"
        method = "POST"
        if edit_original:
            url += "/messages/@original"
            method = "PATCH"
        elif message_id:
            url += f"/messages/{message_id}"
            method = "PATCH"
        elif delete_original:
            url += "/messages/@original"
            method = "DELETE"

        return self._make_discord_request(url, method, json=kwargs if kwargs else None)


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
    input_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "options to use for choice selection. ignored for 'boolean' poll type",
            },
            "details": {"type": "string"},
            "poll_type": {"type": "string", "enum": ["boolean", "choice"]},
            "channel": {
                "type": "number",
                "description": "channel to post the vote in",
            },
            "eligible_voters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "list of users who are eligible to vote. if eligible_voters is provided and channel is not provided, creates vote in a private group message.",
            },
            "ineligible_voters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "list of users who are not eligible to vote",
            },
            "ineligible_voter_message": {
                "type": "string",
                "description": "message to display to ineligible voter when they attempt to cast a vote",
                "default": "You are not eligible to vote in this poll.",
            },
        },
        "required": ["title", "poll_type", "channel"],
    }

    class Meta:
        proxy = True

    def start(self, parameters: Parameters) -> None:
        poll_type = parameters.poll_type
        options = [Bool.YES, Bool.NO] if poll_type == "boolean" else parameters.options
        if options is None:
            raise PluginErrorInternal("Options are required for non-boolean votes")

        self.state.set("parameters", parameters._json)
        self.state.set("poll_type", poll_type)
        self.state.set("options", options)
        self.outcome = {
            "votes": dict([(k, {"users": [], "count": 0}) for k in options]),
        }

        contents = self._construct_content()
        components = self._construct_blocks()
        resp = self.plugin_inst.post_message(text=contents, components=components, channel=parameters.channel)
        logger.debug(resp)

        message_id = resp["id"]
        guild_id = self.plugin.community_platform_id
        self.outcome["message_id"] = message_id
        self.outcome["url"] = f"https://discord.com/channels/{guild_id}/{parameters.channel}/{message_id}"
        self.status = ProcessStatus.PENDING.value
        self.save()

    def _construct_content(self) -> str:
        """
        Construct text content of the vote message, which includes vote counts and usernames of voters
        """
        parameters = self.state.get("parameters")

        content = f"\n**{parameters.get('title')}**\n\n"
        if parameters.get("details"):
            content += f"\n{parameters.get('details')}\n\n"

        poll_type = self.state.get("poll_type")
        options = self.state.get("options")
        votes = self.outcome["votes"]

        option_text_list = []
        for idx, opt in enumerate(options):
            if poll_type == "boolean":
                option_text = f"Approvals" if opt == Bool.YES else "Rejections"
            else:
                option_text = opt

            # show vote count and user list next to each vote option
            num = votes[opt]["count"]
            option_text = f"{option_text}   ({num})"
            if num > 0:
                users = [f"<@{id}>" for id in votes[opt]["users"]]
                users = ", ".join(users)
                option_text = f"{option_text} ({users})"
            option_text_list.append(option_text)

        content += "\n\n".join(option_text_list)
        logger.debug(content)
        return content

    def _construct_blocks(self, hide_buttons=False):
        """
        Construct voting message blocks
        """
        poll_type = self.state.get("poll_type")
        options = self.state.get("options")
        # votes = self.outcome["votes"]

        blocks = []
        for idx, opt in enumerate(options):
            if poll_type == "boolean":
                option_text = ""
                button_emoji = "👍" if opt == Bool.YES else "👎"
            else:
                option_text = opt
                button_emoji = None

            # show vote count and user list next to each vote option
            # num = votes[opt]["count"]
            # option_text = f"{option_text}   ({num})"
            # if num > 0:
            #     users = [f"<@{id}>" for id in votes[opt]["users"]]
            #     users = ", ".join(users)
            #     option_text = f"{option_text} ({users})"

            button = {
                "type": Type.BUTTON,
                "label": option_text,
                "style": 1,
                "custom_id": f"{VOTE_ACTION_ID}_{opt}",
                "disabled": True if hide_buttons else False,
            }
            if button_emoji:
                button["emoji"] = {"name": button_emoji}
            blocks.append(button)

        return [{"type": 1, "components": blocks}]

    def receive_webhook(self, request):
        json_data = json.loads(request.body)
        message_id_to_match = self.outcome["message_id"]
        if not json_data.get("message", {}).get("id") == message_id_to_match:
            return None
        action = json_data["data"]["custom_id"]
        if not action.startswith(VOTE_ACTION_ID):
            return None

        selected_option = action.replace(f"{VOTE_ACTION_ID}_", "")
        user_id = json_data["member"]["user"]["id"]
        username = json_data["member"]["user"]["username"]

        # If user is not eligible to vote, don't cast vote & show an ephemeral message
        if not self._is_eligible_voter(user_id):
            logger.debug(f"Ignoring vote from ineligible voter {user_id}")
            message = self.state.get("parameters").get("ineligible_voter_message")
            return {"type": 4, "data": {"content": message, "flags": 1 << 6}}

        logger.debug(f"> {username} casting vote for {selected_option}")
        self._cast_vote(user_id, selected_option)

        # Respond with updated message, to show votes cast
        content = self._construct_content()
        blocks = self._construct_blocks()
        return {
            "type": 7,  # UPDATE_MESSAGE
            "data": {"content": content, "components": blocks},
        }

    def _is_eligible_voter(self, user):
        eligible_voters = self.state.get("parameters").get("eligible_voters")
        if eligible_voters and user not in eligible_voters:
            return False
        ineligible_voters = self.state.get("parameters").get("ineligible_voters")
        if ineligible_voters and user in ineligible_voters:
            return False
        return True

    def _cast_vote(self, user: str, value: str):
        if not self.outcome["votes"].get(value):
            return False
        if user in self.outcome["votes"][value]["users"]:
            return False

        # Update vote count for selected value
        self.outcome["votes"][value]["users"].append(user)
        self.outcome["votes"][value]["count"] = len(self.outcome["votes"][value]["users"])

        # If user previously voter for a different option, remove old vote
        for k, v in self.outcome["votes"].items():
            if k != value and user in v["users"]:
                v["users"].remove(user)
                v["count"] = len(v["users"])

        self.save()

    def close(self):
        # Set governance process to completed
        self.status = ProcessStatus.COMPLETED.value

        # TODO: update vote message when closed? Interaction tokens are only valid for 15 minutes though.

        self.save()