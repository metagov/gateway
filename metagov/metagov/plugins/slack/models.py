import json
import logging

from rest_framework.exceptions import ValidationError
from metagov.core.plugin_manager import Registry, Parameters, VotingStandard
import requests
from metagov.core.errors import PluginErrorInternal
from metagov.core.models import GovernanceProcess, Plugin, ProcessStatus, AuthType

logger = logging.getLogger(__name__)


@Registry.plugin
class Slack(Plugin):
    name = "slack"
    auth_type = AuthType.OAUTH
    config_schema = {
        "type": "object",
        "properties": {
            # these are set automatically if using the oauth flow
            "team_id": {"description": "Slack Team ID", "type": "string"},
            "team_name": {"description": "Slack Team Name", "type": "string"},
            "bot_token": {"description": "Bot Token", "type": "string"},
            "bot_user_id": {"description": "Bot User ID", "type": "string"},
        },
    }
    community_platform_id_key = "team_id"

    class Meta:
        proxy = True

    def receive_event(self, request):
        """
        Passes on ALL received events to the driver
        """
        json_data = json.loads(request.body)
        if json_data["type"] != "event_callback" or json_data["team_id"] != self.config["team_id"]:
            return

        # Data types: https://api.slack.com/apis/connections/events-api#the-events-api__receiving-events__events-dispatched-as-json
        # Event list: https://api.slack.com/events

        event = json_data["event"]

        # pop off 'type' and 'user' since they are represented separately in metagov-style event
        event_type = event.pop("type")
        maybe_user = event.pop("user", None)

        logger.debug(f"Received event {event_type}")

        initiator = {
            "user_id": maybe_user,
            "provider": "slack",
            "is_metagov_bot": maybe_user and maybe_user == self.config["bot_user_id"],
        }
        self.send_event_to_driver(event_type=event_type, initiator=initiator, data=event)

    @Registry.action(
        slug="post-message",
        input_schema={
            "type": "object",
            "properties": {"users": {"type": "array", "items": {"type": "string"}}, "channel": {"type": "string"}},
        },
        description="Post message either in a channel, direct message, or multi-person message. Supports all params accepted by Slack method chat.postMessage.",
    )
    def post_message(self, users=None, channel=None, **kwargs):
        bot_token = self.config["bot_token"]
        data = {
            "token": bot_token,
            "users": users,
            "channel": channel,
            # note: kwargs may include a token override
            **kwargs,
        }
        if not users and not channel:
            raise ValidationError("users or channel are required")
        if users and not channel:
            # open a conversation for DM or multi person message
            users = ",".join(users)
            params = {"token": bot_token, "users": users}
            response = self.slack_request("POST", "conversations.open", data=params)
            channel = response["channel"]["id"]
            logger.debug(f"Opened conversation {channel} with users {users}")
            data["channel"] = channel
        return self.slack_request("POST", "chat.postMessage", data=data)

    def join_conversation(self, channel):
        return self.slack_request(
            "POST", "conversations.join", data={"token": self.config["bot_token"], "channel": channel}
        )

    @Registry.action(
        slug="method",
        input_schema={
            "type": "object",
            "properties": {"method_name": {"type": "string"}},
            "required": ["method_name"],
        },
        description="Perform any Slack method (provided sufficient scopes)",
    )
    def method(self, method_name, **kwargs):
        """
        Action for performing any method in https://api.slack.com/methods
        See also: https://api.slack.com/web#basics

        Example usage:

        curl -iX POST "https://metagov.policykit.org/api/internal/action/slack.method" -H  "accept: application/json" -H  "X-Metagov-Community: slack-tmq3pkxt9" -d '{"parameters":{"method_name":"chat.postMessage", "channel":"C0177HZTV7X", "text":"hello world"}}'
        curl -iX POST "https://metagov.policykit.org/api/internal/action/slack.method" -H  "accept: application/json" -H  "X-Metagov-Community: slack-tmq3pkxt9" -d '{"parameters":{"channel":"C0177HZTV7X","method":"pins.add","timestamp":"1622820212.008000"}}'
        curl -iX POST "https://metagov.policykit.org/api/internal/action/slack.method" -H  "accept: application/json" -H  "X-Metagov-Community: slack-tmq3pkxt9" -d '{"parameters":{"channel":"C0177HZTV7X","method":"pins.remove","timestamp":"1622820212.008000"}}'
        """
        method = method_name
        # note: parameters may include a token override!
        data = {"token": self.config["bot_token"], **kwargs}
        try:
            return self.slack_request("POST", method, data=data)
        except PluginErrorInternal as e:
            # TODO: make this configurable, might not be desirable in all cases. Bot must be in the channel for `reaction.add` method to work (and others).
            if e.detail == "not_in_channel" and data.get("channel"):
                logger.warn(f"Failed with not_in_channel. Adding bot to channel {data['channel']} and retrying...")
                self.join_conversation(data["channel"])
                return self.slack_request("POST", method, data=data)
            else:
                raise

    def slack_request(self, method, route, json=None, data=None):
        url = f"https://slack.com/api/{route}"
        logger.debug(f"{method} {url}")
        resp = requests.request(method, url, json=json, data=data)
        if not resp.ok:
            logger.error(f"{resp.status_code} {resp.reason}")
            logger.error(resp.request.body)
            raise PluginErrorInternal(resp.text)
        if resp.content:
            data = resp.json()
            is_ok = data.pop("ok")
            if not is_ok:
                # logger.debug(f"X-OAuth-Scopes: {resp.headers.get('X-OAuth-Scopes')}")
                # logger.debug(f"X-Accepted-OAuth-Scopes: {resp.headers.get('X-Accepted-OAuth-Scopes')}")
                # logger.debug(data["error"])
                raise PluginErrorInternal(data["error"])
            return data
        return {}


EMOJI_MAP = {
    "numbers": [
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "keycap_ten",
    ],
    "flowers": [
        "tulip",
        "sunflower",
        "cherry_blossom",
        "rose",
        "wilted_flower",
        "bouquet",
        "hibiscus",
        "blossom",
    ],
    "hearts": [
        "blue_heart",
        "purple_heart",
        "heart",
        "green_heart",
        "sparkling_heart",
        "orange_heart",
        "green_heart",
    ],
}

VOTE_ACTION_ID = "cast_vote"


class Bool:
    YES = "yes"
    NO = "no"


@Registry.governance_process
class SlackEmojiVote(GovernanceProcess):
    # TODO(enhancement): let the caller define the emoji for each option
    # TODO(enhancement): add suport for "closing_at" time
    # TODO(enhancement): support single-choice and multiple-choice
    name = "emoji-vote"
    plugin_name = "slack"
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
                "type": "string",
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
            "emoji_family": {
                "type": "string",
                "enum": ["hearts", "flowers", "numbers"],
                "description": "emoji family to use for choice selection. ignored for 'boolean' poll type",
                "default": "numbers",
            },
        },
        "required": ["title", "poll_type"],
    }

    class Meta:
        proxy = True

    def start(self, parameters: Parameters) -> None:
        text = construct_message_header(parameters.title, parameters.details)
        self.state.set("message_header", text)
        self.state.set("parameters", parameters._json)
        self.state.set("validate", parameters.validate)

        poll_type = parameters.poll_type
        options = [Bool.YES, Bool.NO] if poll_type == "boolean" else parameters.options
        if options is None:
            raise ValidationError("Options are required for non-boolean votes")

        maybe_channel = parameters.channel
        maybe_users = parameters.eligible_voters
        if maybe_channel is None and (maybe_users is None or len(maybe_users) == 0):
            raise ValidationError("eligible_voters or channel are required")

        self.state.set("poll_type", poll_type)
        self.state.set("options", options)
        self.outcome = {
            "votes": dict([(k, {"users": [], "count": 0}) for k in options]),
        }

        blocks = self._construct_blocks()
        blocks = json.dumps(blocks)

        if maybe_channel:
            response = self.plugin_inst.post_message(channel=maybe_channel, blocks=blocks)
        else:
            response = self.plugin_inst.post_message(users=maybe_users, blocks=blocks)

        ts = response["ts"]
        channel = response["channel"]

        permalink_resp = self.plugin_inst.method(method_name="chat.getPermalink", channel=channel, message_ts=ts)

        self.url = permalink_resp["permalink"]
        self.outcome["channel"] = channel
        self.outcome["message_ts"] = ts

        self.status = ProcessStatus.PENDING.value
        self.save()

    def receive_webhook(self, request):
        payload = json.loads(request.POST.get("payload"))
        if payload["message"]["ts"] != self.outcome["message_ts"]:
            return
        logger.info(f"{self} received block action")
        response_url = payload["response_url"]

        for a in payload["actions"]:
            if a["action_id"] == VOTE_ACTION_ID:
                selected_option = a["value"]
                user = payload["user"]["id"]

                # If user is not eligible to vote, don't cast vote & show a message
                if not self._is_eligible_voter(user):
                    message = self.state.get("parameters").get("ineligible_voter_message")
                    logger.debug(f"Ignoring vote from ineligible voter {user}")
                    self.plugin_inst.method(
                        method_name="chat.postEphemeral", channel=self.outcome["channel"], text=message, user=user
                    )
                    return

                self._cast_vote(user, selected_option)

        # Update vote message to show votes cast
        blocks = self._construct_blocks()
        blocks = json.dumps(blocks)
        requests.post(response_url, json={"replace_original": "true", "blocks": blocks})

    def _cast_vote(self, user: str, value: str):
        if not self.outcome["votes"].get(value):
            return False
        if user in self.outcome["votes"][value]["users"]:
            return False

        # Update vote count for selected value
        logger.debug(f"> {user} cast vote for {value}")
        self.outcome["votes"][value]["users"].append(user)
        self.outcome["votes"][value]["count"] = len(self.outcome["votes"][value]["users"])

        # If user previously voter for a different option, remove old vote
        for k, v in self.outcome["votes"].items():
            if k != value and user in v["users"]:
                v["users"].remove(user)
                v["count"] = len(v["users"])

        self.save()

    def _is_eligible_voter(self, user):
        eligible_voters = self.state.get("parameters").get("eligible_voters")
        if eligible_voters and user not in eligible_voters:
            return False
        ineligible_voters = self.state.get("parameters").get("ineligible_voters")
        if ineligible_voters and user in ineligible_voters:
            return False
        return True

    def _construct_blocks(self, hide_buttons=False):
        """
        Construct voting message blocks
        """
        text = self.state.get("message_header")
        poll_type = self.state.get("poll_type")
        options = self.state.get("options")
        votes = self.outcome["votes"]

        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
        for idx, opt in enumerate(options):
            if poll_type == "boolean":
                option_text = f"Approve" if opt == Bool.YES else "Reject"
                button_text = f":+1:" if opt == Bool.YES else ":-1:"
            else:
                option_text = opt
                family = self.state.get("parameters")["emoji_family"]
                button_text = f":{EMOJI_MAP[family][idx]}:"

            # show vote count and user list next to each vote option
            num = votes[opt]["count"]
            option_text = f"{option_text}   `{num}`"
            if num > 0:
                users = [f"<@{id}>" for id in votes[opt]["users"]]
                users = ", ".join(users)
                option_text = f"{option_text} ({users})"

            vote_option_section = {"type": "section", "text": {"type": "mrkdwn", "text": option_text}}
            if not hide_buttons:
                vote_option_section["accessory"] = {
                    "type": "button",
                    "text": {"type": "plain_text", "text": button_text, "emoji": True},
                    "value": opt,
                    "action_id": VOTE_ACTION_ID,
                }
            blocks.append(vote_option_section)
        return blocks

    def close(self):
        # Set governnace process to completed
        self.status = ProcessStatus.COMPLETED.value

        # Update vote message to hide voting buttons
        blocks = self._construct_blocks(hide_buttons=True)
        self.plugin_inst.method(
            method_name="chat.update",
            channel=self.outcome["channel"],
            ts=self.outcome["message_ts"],
            blocks=json.dumps(blocks),
        )
        self.save()


def construct_message_header(title, details=None):
    text = f"*{title}*\n"
    if details:
        text += f"{details}\n"
    return text


ADVANCED_VOTE_ACTION_ID = "advanced_vote"
CONFIRM_ADVANCED_VOTE = "confirm"

@Registry.governance_process
class SlackAdvancedVote(GovernanceProcess):
    name = "advanced-vote"
    plugin_name = "slack"
    input_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "candidates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "a list of candidates to vote for; for each we will create a select button",
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "a predefined options for users to select from",
            },
            "channel": {
                "type": "string",
                "description": "channel to post the vote in",
            }
        },
        "required": ["title", "channel"],
    }

    class Meta:
        proxy = True

    def start(self, parameters: Parameters) -> None:
        text = construct_message_header(parameters.title)
        self.state.set("message_header", text)
        self.state.set("candidates", parameters.candidates)
        self.state.set("parameters", parameters._json)

        options = parameters.options
        if options is None:
            raise ValidationError("Options are required for advanced votes")

        maybe_channel = parameters.channel
        if maybe_channel is None:
            raise ValidationError("eligible_voters or channel are required")
        
        self.state.set("options", options)
        self.outcome = {"votes": {}}

        blocks = self._construct_blocks()
        blocks = json.dumps(blocks)

        response = self.plugin_inst.post_message(channel=maybe_channel, blocks=blocks)

        ts = response["ts"]
        channel = response["channel"]

        permalink_resp = self.plugin_inst.method(method_name="chat.getPermalink", channel=channel, message_ts=ts)

        self.url = permalink_resp["permalink"]
        self.outcome["channel"] = channel
        self.outcome["message_ts"] = ts

        self.status = ProcessStatus.PENDING.value
        self.save()
    
    def receive_webhook(self, request):
        payload = json.loads(request.POST.get("payload"))
        
        if payload["message"]["ts"] != self.outcome["message_ts"]:
            return

        logger.debug(f"payload received")
        for key, value in payload.items():
            logger.debug(f"{key}: \t{value}")
        logger.info(f"{self} received block action")
        response_url = payload["response_url"]

        for a in payload["actions"]:
            if a["action_id"].startswith(ADVANCED_VOTE_ACTION_ID):
                candidate = a["action_id"].split(".")[1]
                selected_option = a["selected_option"]["value"]
                user = payload["user"]["id"]

                # If user is not eligible to vote, don't cast vote & show a message
                if not self._is_eligible_voter(user):
                    # message = self.state.get("parameters").get("ineligible_voter_message")
                    # logger.debug(f"Ignoring vote from ineligible voter {user}")
                    # self.plugin_inst.method(
                    #     method_name="chat.postEphemeral", channel=self.outcome["channel"], text=message, user=user
                    # )
                    return

                self._cast_vote(user, candidate, selected_option)

    def _is_eligible_voter(self, user):
        return True 

    def _cast_vote(self, user: str, candidate: str, option: str):
        # Update vote count for selected value
        logger.debug(f"> {user} cast vote {option} for {candidate}")
        if user not in self.outcome["votes"]:
            self.outcome["votes"][user] = {}
        self.outcome["votes"][user][candidate] = option
        self.save()

    def _construct_blocks(self, hide_buttons=False):
        """
        Construct voting message blocks
        """
        text = self.state.get("message_header")
        candidates = self.state.get("candidates")
        options = self.state.get("options")
        votes = self.outcome["votes"]

        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
        for idx, candidate in enumerate(candidates):
            candidate_text = candidate
            action_id = f"{ADVANCED_VOTE_ACTION_ID}.{candidate}"
            vote_option_section = {"type": "section", "text": {"type": "mrkdwn", "text": candidate_text}}
            vote_option_section["accessory"] = {
                "action_id": action_id,
                "type": "static_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select an option"
                },
                "options": []
            }
            for idx, option in enumerate(options):
                vote_option_section["accessory"]["options"].append({
                    "text": {
                        "type": "plain_text",
                        "text": option
                    },
                    "value": option
                })
            blocks.append(vote_option_section)
        
        blocks.append({
			"type": "actions",
			"elements": [
				{
					"type": "button",
					"text": {
						"type": "plain_text",
						"text": "Confirm"
					},
					"value": "confirm",
					"action_id": CONFIRM_ADVANCED_VOTE
				}
			]
		})
        return blocks

    def close(self):
        # Set governnace process to completed
        self.status = ProcessStatus.COMPLETED.value
        self.save()