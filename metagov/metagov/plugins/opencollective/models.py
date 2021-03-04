
import requests
import logging
import metagov.plugins.opencollective.queries as Queries
import metagov.plugins.opencollective.schemas as Schemas
from metagov.core.plugin_models import (load_settings,
                                        retrieve_resource,
                                        register_action)

logger = logging.getLogger('django')
settings = load_settings("opencollective")

api_key = settings['opencollective_api_key']

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


# init - do this somewhere else
result = run_query(Queries.collective, {'slug': collective})
logger.info(result)
collective_id = result['data']['collective']['id']
collective_name = result['data']['collective']['name']


@register_action(
    action_type="opencollective.create-conversation",
    description="Start a new conversation on Open Collective",
    parameters_schema=Schemas.create_conversation_parameters,
    response_schema=Schemas.create_conversation_response,
)
def create_conversation(initiator, parameters):
    variables = {
        "html": parameters['raw'],
        # "tags": [],
        "title": parameters['title'],
        "CollectiveId": collective_id
    }
    result = run_query(Queries.create_conversation, variables)
    data = result['data']['createConversation']
    url = f"{opencollective_url}/{collective}/conversations/{data['slug']}-{data['id']}"
    return {'url': url, 'conversation_id': data['id']}


@register_action(
    action_type="opencollective.create-comment",
    description="Add a comment to a conversation on Open Collective",
    parameters_schema=Schemas.create_comment_parameters,
    response_schema=Schemas.create_comment_response,
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


@retrieve_resource('collective-members', 'members of the collective')
def get_members(request):
    from django.http import JsonResponse
    result = run_query(Queries.members, {'slug': collective})
    accounts = [a['account']
                for a in result['data']['collective']['members']['nodes']]
    return JsonResponse({'accounts': accounts})
