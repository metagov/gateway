
import requests
import logging
import json
import time
import metagov.plugins.opencollective.queries as Queries
import metagov.plugins.opencollective.schemas as Schemas
from metagov.core.plugin_models import (load_settings,
                                        register_resource,
                                        register_listener,
                                        register_action,
                                        send_platform_event,
                                        BaseCommunity,
                                        BaseUser)

logger = logging.getLogger('django')
settings = load_settings("opencollective")

api_key = settings['opencollective_api_key']
webhook_receiver_slug = settings['opencollective_webhook_receiver_slug']

opencollective_url = "https://opencollective.com"
# from settings
collective = "metagov"


def run_query(query, variables):
    request = requests.post(
        "https://api.opencollective.com/graphql/v2", json={'query': query, 'variables': variables}, headers={"Api-Key": f"{api_key}"})
    if request.status_code == 200:
        return request.json()
    else:
        logger.info(request.text)
        raise Exception("Query failed to run by returning code of {} {}. {}".format(
            request.status_code, request.reason, query))


class OpenCollectiveUser(BaseUser):
    pass


class OpenCollectiveCommunity(BaseCommunity):
    def __init__(self,
                 name: str,
                 slug: str,
                 collective_id: str,
                 collective_legacy_id: int):
        self.platform = 'opencollective'
        self.name = name
        self.unique_id = slug
        self.slug = slug
        self.collective_id = collective_id
        self.collective_legacy_id = collective_legacy_id


def create_community():
    result = run_query(Queries.collective, {'slug': collective})
    logger.info("Initialized Open Collective: " + str(result))
    return OpenCollectiveCommunity(
        name=result['data']['collective']['name'],
        slug=collective,
        collective_id=result['data']['collective']['id'],
        collective_legacy_id=result['data']['collective']['legacyId']
    )


# init - do this somewhere else
community = create_community()


"""
ACTIONS
"""


@register_action(
    slug="opencollective.create-conversation",
    description="Start a new conversation on Open Collective",
    input_schema=Schemas.create_conversation_parameters,
    output_schema=Schemas.create_conversation_response,
)
def create_conversation(initiator, parameters):
    variables = {
        "html": parameters['raw'],
        # "tags": [],
        "title": parameters['title'],
        "CollectiveId": community.collective_id
    }
    result = run_query(Queries.create_conversation, variables)
    data = result['data']['createConversation']
    url = f"{opencollective_url}/{collective}/conversations/{data['slug']}-{data['id']}"
    return {'url': url, 'conversation_id': data['id']}


@register_action(
    slug="opencollective.create-comment",
    description="Add a comment to a conversation on Open Collective",
    input_schema=Schemas.create_comment_parameters,
    output_schema=Schemas.create_comment_response,
)
def create_comment(initiator, parameters):
    variables = {
        "comment": {
            "html": parameters['raw'],
            "ConversationId": parameters['conversation_id']
        }
    }
    result = run_query(Queries.create_comment, variables)
    data = result['data']['createComment']
    logger.info(data)
    return {'comment_id': data['id']}


"""
LISTENER
"""


@register_listener(
    slug=webhook_receiver_slug,
    description="receive events from Open Collective")
def listener(request):
    body = json.loads(request.body)
    if body.get('CollectiveId') != community.collective_legacy_id:
        raise Exception(
            f"Received webhook for the wrong collective. Expected {community.collective_legacy_id}, found " + str(body.get('CollectiveId')))

    event_type = body.get("type")
    if event_type == "collective.expense.created":
        # Hit API to get expense data
        variables = {
            "reference": {
                'legacyId': body['data']['expense']['id']
            }
        }
        expense_data = run_query(Queries.expense, variables)['data']['expense']
        username = expense_data['createdByAccount']['slug']
        send_platform_event(
            event_type="expense_created",
            community=community,
            initiator=OpenCollectiveUser(username=username),
            data=expense_data
        )


"""
RESOURCE RETRIEVALS
"""


@register_resource(slug='opencollective.members', description='list members of the collective')
def get_members(_parameters):
    result = run_query(Queries.members, {'slug': collective})
    accounts = [a['account']
                for a in result['data']['collective']['members']['nodes']]
    return {'accounts': accounts}
