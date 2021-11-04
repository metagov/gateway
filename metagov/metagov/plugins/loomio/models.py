import json
import logging

from metagov.core.plugin_manager import Registry, Parameters, VotingStandard
import metagov.plugins.loomio.schemas as Schemas
import requests
from metagov.core.errors import PluginErrorInternal
from metagov.core.models import GovernanceProcess, Plugin, ProcessStatus, AuthType

logger = logging.getLogger(__name__)


@Registry.plugin
class Loomio(Plugin):
    name = "loomio"
    auth_type = AuthType.API_KEY
    config_schema = {
        "type": "object",
        "properties": {
            "api_key": {"type": "string"},
            "subgroup_api_keys": {"type": "array", "items": {"type": "string"}},
            "webhook_slug": {"type": "string"},
        },
        "required": ["api_key"],
    }

    class Meta:
        proxy = True

    def initialize(self):
        # Map API keys -> handle ("metagov-testing") and key ("2qE8dI91")
        api_key_group_map = {}
        all_api_keys = self.config.get("subgroup_api_keys") or []
        all_api_keys.append(self.config["api_key"])
        for api_key in all_api_keys:
            group = self._get_memberships(api_key)["groups"][0]
            api_key_group_map[api_key] = {"key": group["key"], "handle": group["handle"]}

        self.state.set("api_key_group_map", api_key_group_map)

        # Set the community_platform_id to the main group handle
        parent_group_handle = api_key_group_map[self.config["api_key"]]["handle"]
        self.community_platform_id = parent_group_handle
        self.save()

    def _get_api_key(self, key_or_handle):
        """Get the API key for a specific Loomio group. Returns None if not found."""
        api_key_group_map = self.state.get("api_key_group_map")
        for api_key, v in api_key_group_map.items():
            if v["key"] == key_or_handle or v["handle"] == key_or_handle:
                return api_key
        return None

    def _get_memberships(self, api_key):
        resp = requests.get(f"https://www.loomio.org/api/b1/memberships?api_key={api_key}")
        if not resp.ok:
            logger.error(f"Error: {resp.status_code} {resp.text}")
            raise PluginErrorInternal(resp.text)
        return resp.json()

    @Registry.action(
        slug="list-members",
        description="list groups and users",
        input_schema={
            "type": "object",
            "properties": {
                "subgroup": {
                    "type": "string",
                    "description": "subgroup to list membership of. can be the loomio key or the loomio handle. only works if plugin is configured with an API key for this subgroup.",
                }
            },
        },
    )
    def list_members(self, subgroup=None):
        if subgroup:
            api_key = self._get_api_key(subgroup)
        else:
            api_key = self.config["api_key"]
        return self._get_memberships(api_key)

    @Registry.action(
        slug="create-discussion",
        description="create a new discussion",
        input_schema=Schemas.create_discussion_input,
    )
    def create_discussion(self, title, subgroup=None, **kwargs):
        payload = {"title": title, **kwargs}
        if subgroup:
            payload["api_key"] = self._get_api_key(subgroup)
        else:
            payload["api_key"] = self.config["api_key"]

        resp = requests.post(f"https://www.loomio.org/api/b1/discussions", payload)
        if not resp.ok:
            logger.error(f"Error: {resp.status_code} {resp.text}")
            raise PluginErrorInternal(resp.text)
        response = resp.json()
        return response

    @Registry.webhook_receiver()
    def loomio_webhook(self, request):
        pass


@Registry.governance_process
class LoomioPoll(GovernanceProcess):
    name = "poll"
    plugin_name = "loomio"
    input_schema = Schemas.start_loomio_poll

    class Meta:
        proxy = True

    def start(self, parameters: Parameters):
        url = "https://www.loomio.org/api/b1/polls"
        payload = parameters._json
        payload.pop("options")

        subgroup = payload.pop("subgroup", None)
        api_key = self.plugin_inst._get_api_key(subgroup) if subgroup else self.plugin_inst.config["api_key"]
        self.state.set("poll_api_key", api_key)

        payload["options[]"] = parameters.options
        payload["api_key"] = api_key
        resp = requests.post(url, payload)
        if not resp.ok:
            logger.error(f"Error: {resp.status_code} {resp.text}")
            raise PluginErrorInternal(resp.text)

        response = resp.json()

        if response.get("errors"):
            errors = response["errors"]
            raise PluginErrorInternal(str(errors))

        poll_key = response.get("polls")[0].get("key")
        poll_url = f"https://www.loomio.org/p/{poll_key}"
        self.state.set("poll_key", poll_key)
        self.outcome = {"poll_url": poll_url}
        self.status = ProcessStatus.PENDING.value
        self.save()

    def receive_webhook(self, request):
        poll_key = self.state.get("poll_key")
        poll_url = self.outcome.get("poll_url")

        body = json.loads(request.body)
        url = body.get("url")
        if url is None or not url.startswith(poll_url):
            return
        kind = body.get("kind")
        logger.info(f"Processing event '{kind}' for poll {url}")
        if kind == "poll_closed_by_user" or kind == "poll_expired":
            logger.info(f"Loomio poll closed. Fetching poll result...")
            self.fetch_and_update_outcome()
            assert self.status == ProcessStatus.COMPLETED.value
        elif kind == "stance_created":
            # update each time a vote is cast, so that the driver can decide when to close the vote based on threshold if desired
            self.fetch_and_update_outcome()

    def fetch_and_update_outcome(self):
        poll_key = self.state.get("poll_key")
        api_key = self.state.get("poll_api_key")
        url = f"https://www.loomio.org/api/b1/polls/{poll_key}?api_key={api_key}"
        resp = requests.get(url)
        if not resp.ok:
            logger.error(f"Error fetching poll: {resp.status_code} {resp.text}")
            raise PluginErrorInternal(resp.text)

        logger.debug(resp.text)
        response = resp.json()
        if response.get("errors"):
            logger.error(f"Error fetching poll outcome: {response['errors']}")
            self.errors = response["errors"]

        # Update status
        poll = response["polls"][0]
        if poll.get("closed_at") is not None:
            self.status = ProcessStatus.COMPLETED.value

        # Update vote counts
        self.outcome["votes"] = create_vote_dict(response)

        # Add other data from poll
        self.outcome["voters_count"] = poll.get("voters_count")
        self.outcome["undecided_voters_count"] = poll.get("undecided_voters_count")
        self.outcome["cast_stances_pct"] = poll.get("cast_stances_pct")

        logger.info(f"Updated outcome: {self.outcome}")
        self.save()


def create_vote_dict(response):
    poll_options = response["poll_options"]
    result = {}
    for opt in poll_options:
        result[opt["name"]] = {"count": opt["total_score"], "users": list(opt["voter_scores"].keys())}
    return result