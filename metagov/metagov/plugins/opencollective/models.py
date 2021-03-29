import json
import logging

import metagov.core.plugin_decorators as Registry
import metagov.plugins.opencollective.queries as Queries
import metagov.plugins.opencollective.schemas as Schemas
import requests
from metagov.core.models import Plugin

logger = logging.getLogger("django")

opencollective_url = "https://opencollective.com"


@Registry.plugin
class OpenCollective(Plugin):
    name = "opencollective"
    config_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "api_key": {"type": "string"},
            "collective_slug": {
                "type": "string",
                "description": "Slug for the Open Collective collective (opencollective.com/<slug>)",
            },
            "webhook_slug": {"type": "string"},
        },
        "required": ["api_key", "collective_slug"],
    }

    class Meta:
        proxy = True

    def initialize(self):
        slug = self.config["collective_slug"]
        response = self.run_query(Queries.collective, {"slug": slug})
        result = response["data"]["collective"]

        logger.info("Initialized Open Collective: " + str(result))

        self.state.set("collective_name", result["name"])
        self.state.set("collective_id", result["id"])
        self.state.set("collective_legacy_id", result["legacyId"])

    def run_query(self, query, variables):
        api_key = self.config["api_key"]
        request = requests.post(
            "https://api.opencollective.com/graphql/v2",
            json={"query": query, "variables": variables},
            headers={"Api-Key": f"{api_key}"},
        )
        if request.status_code == 200:
            return request.json()
        else:
            logger.info(request.text)
            raise Exception(
                "Query failed to run by returning code of {} {}. {}".format(request.status_code, request.reason, query)
            )

    @Registry.resource(
        slug="members",
        description="list members of the collective",
    )
    def get_members(self, _parameters):
        result = self.run_query(Queries.members, {"slug": self.config["collective_slug"]})
        accounts = [a["account"] for a in result["data"]["collective"]["members"]["nodes"]]
        return {"accounts": accounts}

    @Registry.action(
        slug="create-conversation",
        description="Start a new conversation on Open Collective",
        input_schema=Schemas.create_conversation_parameters,
        output_schema=Schemas.create_conversation_response,
    )
    def create_conversation(self, parameters, initiator):
        variables = {
            "html": parameters["raw"],
            # "tags": [],
            "title": parameters["title"],
            "CollectiveId": self.state.get("collective_id"),
        }
        result = self.run_query(Queries.create_conversation, variables)
        data = result["data"]["createConversation"]
        url = f"{opencollective_url}/{self.config['collective_slug']}/conversations/{data['slug']}-{data['id']}"
        return {"url": url, "conversation_id": data["id"]}

    @Registry.action(
        slug="create-comment",
        description="Add a comment to a conversation on Open Collective",
        input_schema=Schemas.create_comment_parameters,
        output_schema=Schemas.create_comment_response,
    )
    def create_comment(self, parameters, initiator):
        variables = {"comment": {"html": parameters["raw"], "ConversationId": parameters["conversation_id"]}}
        result = self.run_query(Queries.create_comment, variables)
        data = result["data"]["createComment"]
        logger.info(data)
        return {"comment_id": data["id"]}

    def receive_webhook(self, request):
        body = json.loads(request.body)
        collective_legacy_id = self.state.get("collective_legacy_id")
        if body.get("CollectiveId") != collective_legacy_id:
            raise Exception(
                f"Received webhook for the wrong collective. Expected {collective_legacy_id}, found "
                + str(body.get("CollectiveId"))
            )

        event_type = body.get("type")
        if event_type == "collective.expense.created":
            # Hit API to get expense data
            variables = {"reference": {"legacyId": body["data"]["expense"]["id"]}}
            expense_data = self.run_query(Queries.expense, variables)["data"]["expense"]
            initiator = {"user_id": expense_data["createdByAccount"]["slug"], "provider": "opencollective"}
            self.send_event_to_driver(event_type="expense_created", initiator=initiator, data=expense_data)
