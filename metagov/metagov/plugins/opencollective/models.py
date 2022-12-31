import json
import logging
from django.conf import settings

from metagov.core.plugin_manager import Registry, Parameters
import metagov.plugins.opencollective.queries as Queries
import metagov.plugins.opencollective.schemas as Schemas
import requests
from metagov.core.errors import PluginErrorInternal
from metagov.core.models import GovernanceProcess, Plugin, ProcessStatus, AuthType

logger = logging.getLogger(__name__)

USE_STAGING = settings.METAGOV_SETTINGS.get("OPENCOLLECTIVE", {}).get("USE_STAGING", False)


if USE_STAGING:
    OPEN_COLLECTIVE_URL = "https://staging.opencollective.com"
    OPEN_COLLECTIVE_GRAPHQL = "https://staging.opencollective.com/api/graphql/v2"
else:
    OPEN_COLLECTIVE_URL = "https://opencollective.com"
    OPEN_COLLECTIVE_GRAPHQL = "https://api.opencollective.com/graphql/v2"


@Registry.plugin
class OpenCollective(Plugin):
    name = "opencollective"
    auth_type = AuthType.OAUTH
    config_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "access_token": {"type": "string", "description": "Access token for Open Collective account"},
            "collective_slug": {
                "type": "string",
                "description": "Open Collective slug",
            },
        },
        "required": ["access_token", "collective_slug"],
    }
    community_platform_id_key = "collective_slug"

    class Meta:
        proxy = True

    def initialize(self):
        # Fetch info about collective
        slug = self.config["collective_slug"]
        response = self.run_query(Queries.collective, {"slug": slug})
        result = response["collective"]
        if result is None:
            raise PluginErrorInternal(f"Collective '{slug}' not found.")

        # Create webhook for listening to events on OC
        self.create_webhook()

        # Store collective information in plugin state
        self.state.set("collective_name", result["name"])
        self.state.set("collective_id", result["id"])
        self.state.set("collective_legacy_id", result["legacyId"])
        project_legacy_ids = []
        if result.get("childrenAccounts"):
            project_legacy_ids = [
                node["legacyId"] for node in result["childrenAccounts"]["nodes"] if node["type"] == "PROJECT"
            ]

        self.state.set("project_legacy_ids", project_legacy_ids)
        logger.info("Initialized Open Collective: " + str(result))

    def run_query(self, query, variables):
        resp = requests.post(
            OPEN_COLLECTIVE_GRAPHQL,
            json={"query": query, "variables": variables},
            headers={"Authorization": f"Bearer {self.config['access_token']}"},
        )
        if not resp.ok:
            logger.error(f"Query failed with {resp.status_code} {resp.reason}: {query}")
            raise PluginErrorInternal(resp.text)

        result = resp.json()
        if result.get("errors"):
            msg = ",".join([e["message"] for e in result["errors"]])
            raise PluginErrorInternal(msg)
        return result["data"]

    def create_webhook(self):
        webhook_url = f"{settings.SERVER_URL}/api/hooks/{self.name}/{self.community.slug}"
        logger.debug(f"Creating OC webhook: {webhook_url}")
        resp = self.run_query(Queries.create_webhook, {
            "webhook": {
                "account": {
                    "slug": self.config["collective_slug"]
                },
                "activityType": "ACTIVITY_ALL",
                "webhookUrl": webhook_url
            }
        })
        result = resp.json()
        logger.debug(result)

    @Registry.action(slug="list-members", description="list members of the collective")
    def list_members(self):
        result = self.run_query(Queries.members, {"slug": self.config["collective_slug"]})
        accounts = [a["account"] for a in result["collective"]["members"]["nodes"]]
        return {"accounts": accounts}

    @Registry.action(
        slug="create-conversation",
        description="Start a new conversation on Open Collective",
        input_schema=Schemas.create_conversation,
    )
    def create_conversation(self, raw, title, tags=None):
        variables = {
            "html": raw,
            "title": title,
            "tags": tags or [],
            "CollectiveId": self.state.get("collective_id"),
        }
        result = self.run_query(Queries.create_conversation, variables)
        conversation_data = result["createConversation"]
        self.add_conversation_url(conversation_data)
        return conversation_data

    @Registry.action(
        slug="create-comment",
        description="Add a comment to a conversation or expense on Open Collective",
        input_schema=Schemas.create_comment,
    )
    def create_comment(self, raw, conversation_id=None, expense_id=None):
        comment = {"html": raw}
        if conversation_id:
            comment["ConversationId"] = conversation_id
        if expense_id:
            comment["expense"] = {"id": expense_id}
        result = self.run_query(Queries.create_comment, {"comment": comment})
        comment_data = result["createComment"]
        return comment_data

    @Registry.action(
        slug="process-expense",
        description="Approve, unapprove, or reject expense",
        input_schema=Schemas.process_expense,
    )
    def process_expense(self, expense_id, action):
        variables = {
            "reference": {"id": expense_id},
            "action": action,  # APPROVE, UNAPPROVE, or REJECT
        }
        result = self.run_query(Queries.process_expense, variables)
        expense_data = result["processExpense"]
        self.add_expense_url(expense_data)
        return expense_data

    def __validate_collective_or_project(self, legacy_id):
        if legacy_id == self.state.get("collective_legacy_id"):
            return True
        project_legacy_ids = self.state.get("project_legacy_ids") or []
        if legacy_id in project_legacy_ids:
            return True
        # re-initialize and check projects again, in case a new project has been added
        self.initialize()
        project_legacy_ids = self.state.get("project_legacy_ids")
        if legacy_id in project_legacy_ids:
            return True
        raise PluginErrorInternal(
            f"Received webhook for the wrong collective. Expected {self.state.get('collective_legacy_id')} or projects {project_legacy_ids}, found "
            + str(legacy_id)
        )

    @Registry.webhook_receiver()
    def process_oc_webhook(self, request):
        body = json.loads(request.body)
        self.__validate_collective_or_project(body.get("CollectiveId"))

        event_type = body.get("type")

        logger.debug(f"Received Open Collective event '{event_type}': {body}")

        if event_type.startswith("collective.expense."):
            expense_event = event_type.replace("collective.expense.", "")
            event_name = f"expense_{expense_event}"
            # Hit API to get expense data
            expense_data = self.get_expense_data(body["data"]["expense"]["id"])

            if expense_event == "created":
                initiator = {"user_id": expense_data["createdByAccount"]["slug"], "provider": "opencollective"}
            else:
                # find the expense activity that corresponds to this event
                activity = [a for a in expense_data["activities"] if a["createdAt"] == body["createdAt"]]
                initiator = {"user_id": activity[0].get("individual", {}).get("slug"), "provider": "opencollective"}

            self.send_event_to_driver(event_type=event_name, initiator=initiator, data=expense_data)

    def get_expense_data(self, legacy_id: str):
        variables = {"reference": {"legacyId": legacy_id}}
        expense_data = self.run_query(Queries.expense, variables)["expense"]
        self.add_expense_url(expense_data)
        return expense_data

    def add_expense_url(self, expense):
        collective_slug = self.config["collective_slug"]
        # Account will be different from Collective IF the expense was subitted in a project
        account_slug = expense.get("account", {}).get("slug")
        account_route = f"{collective_slug}/{account_slug}" if account_slug != collective_slug else collective_slug

        url = f"{OPEN_COLLECTIVE_URL}/{account_route}/expenses/{expense['legacyId']}"
        expense["url"] = url

    def add_conversation_url(self, conversation):
        url = f"{OPEN_COLLECTIVE_URL}/{self.config['collective_slug']}/conversations/{conversation['slug']}-{conversation['id']}"
        conversation["url"] = url


@Registry.governance_process
class OpenCollectiveVote(GovernanceProcess):
    name = "vote"
    plugin_name = "opencollective"

    input_schema = {
        "type": "object",
        "properties": {"title": {"type": "string"}, "details": {"type": "string"}},
        "required": ["title"],
    }
    YES = "yes"
    NO = "no"

    THUMBS_UP_UTF8 = b"\xf0\x9f\x91\x8d\xef\xb8\x8f"
    THUMBS_DOWN_UTF8 = b"\xf0\x9f\x91\x8e"

    class Meta:
        proxy = True

    def start(self, parameters: Parameters) -> None:
        result = self.plugin_inst.create_conversation(
            raw=parameters.details, title=parameters.title, tags="metagov-vote"
        )
        self.url = result["url"]
        logger.info(f"Poll created at {self.url}")

        self.state.set("id", result["id"])
        self.state.set("title", result["title"])

        self.outcome = {"votes": {self.YES: 0, self.NO: 0}}

        result = self.plugin_inst.run_query(Queries.conversation, {"id": self.state.get("id")})
        data = result["conversation"]
        self.update_outcome_from_conversation(data)

        self.status = ProcessStatus.PENDING.value
        self.save()

    def update(self):
        result = self.plugin_inst.run_query(Queries.conversation, {"id": self.state.get("id")})
        data = result["conversation"]
        self.update_outcome_from_conversation(data)

    def close(self):
        logger.info("Closing Open Collective vote...'")
        self.update()  # update self.outcome to most recent vote count

        # change conversation title
        conversation_id = self.state.get("id")
        new_title = "[CLOSED] " + self.state.get("title")
        result = self.plugin_inst.run_query(Queries.edit_conversation, {"id": conversation_id, "title": new_title})

        # add a comment
        votes = self.outcome["votes"]
        yes_votes = votes[self.YES]
        no_votes = votes[self.NO]
        self.plugin_inst.create_comment(
            # TODO: Driver should be able to customize this msg for each process instance. Include template in input_schema?
            raw=f"Voting period is closed. Final count is {yes_votes} for and {no_votes} against.",
            conversation_id=conversation_id,
        )
        self.status = ProcessStatus.COMPLETED.value
        self.save()

    def update_outcome_from_conversation(self, conversation):
        """Save changes to outcome and state if changed"""
        # get reaction count for thumbs-up and thumbs-down
        reactions = {k.encode("utf-8"): v for (k, v) in conversation["body"]["reactions"].items()}
        yes_count = reactions.get(self.THUMBS_UP_UTF8, 0)
        no_count = reactions.get(self.THUMBS_DOWN_UTF8, 0)

        # update vote count in outcome
        votes = self.outcome["votes"]
        votes[self.YES] = yes_count
        votes[self.NO] = no_count

        self.outcome["votes"] = votes
        self.save()
