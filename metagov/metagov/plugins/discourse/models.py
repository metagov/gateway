import json
import logging
import jsonpickle
import requests
from drf_yasg import openapi
import metagov.plugins.discourse.schemas as Schemas
from metagov.core.plugin_models import (GovernanceProcessProvider,
                                        ProcessState, ProcessStatus,
                                        load_settings,
                                        webhook_listener,
                                        BaseCommunity,
                                        BaseUser,
                                        retrieve_resource,
                                        PlatformEvent,
                                        register_action)


logger = logging.getLogger('django')

settings = load_settings("discourse")

discourse_server_url = settings['discourse_url']
system_api_key = settings['discourse_api_key']


def construct_post_url(post):
    return f"{discourse_server_url}/t/{post['topic_slug']}/{post['topic_id']}/{post['post_number']}?u={post['username']}"


class DiscourseUser(BaseUser):
    pass


class DiscourseCommunity(BaseCommunity):
    def __init__(self,
                 name: str,
                 server_url: str):
        self.platform = 'discourse'
        self.name = name
        self.unique_id = server_url


def create_discourse_community():
    resp = requests.get(f"{discourse_server_url}/about.json")
    response = resp.json()
    community_name = response.get('about').get('title')
    return DiscourseCommunity(name=community_name, server_url=discourse_server_url)


# init - do this somewhere else
community = create_discourse_community()


def make_discourse_request(route, payload):
    headers = {
        'Content-Type': 'application/json',
        'Api-Username': 'system',
        'Api-Key': system_api_key
    }
    resp = requests.post(f"{discourse_server_url}/{route}",
                         headers=headers, json=payload)
    if not resp.ok:
        logger.info(resp)
        logger.error(f"{resp.status_code} {resp.reason}")
        raise ValueError(resp.text)
    return resp.json()


"""
ACTIONS
"""


@register_action(
    action_type="discourse.create-post",
    description="Create a new post on discourse",
    parameters_schema=Schemas.create_post_parameters,
    response_schema=Schemas.create_post_response,
)
def create_post(initiator, parameters):
    payload = {'raw': parameters['raw'], 'topic_id': parameters['topic_id']}
    post = make_discourse_request("posts.json", payload)
    return {'url': construct_post_url(post)}


"""
LISTENERS
"""


@webhook_listener("discourse", "receive events")
def process_webhook(request):
    instance = request.headers.get('X-Discourse-Instance')
    event_id = request.headers.get('X-Discourse-Event-Id')
    event_type = request.headers.get('X-Discourse-Event-Type')
    event = request.headers.get('X-Discourse-Event')
    logger.info(f"Received event {event} from {instance}")
    body = json.loads(request.body)
    logger.info(body)
    if instance != discourse_server_url:
        raise Exception("got webhook event that doesnt match server")
    new_action = None
    if event == "post_created":
        post = body.get('post')
        data = {'raw': post['raw'], 'topic_id': post['topic_id'], 'url': construct_post_url(post)}
        initiator = DiscourseUser(username=post['username'])
        new_action = PlatformEvent(
            community=community,
            event_type="post_created",
            initiator=initiator,
            timestamp="time",
            data=data
        )
    else:
        logger.info("not creating any action from webhook")

    if new_action:
        logger.info("Sending action to Driver: " + new_action.toJSON())
        new_action.send()


"""
RESOURCE RETRIEVALS
"""


@retrieve_resource('badges', 'Discourse badges for a given user')
def get_discourse_badges(request):
    raise NotImplementedError


"""
GOVERNANCE PROCESSES
"""


class DiscoursePoll(GovernanceProcessProvider):
    slug = 'discourse-poll'

    #TODO use jsonschema-to-openapi
    input_schema = {
        'properties': {
            "title": openapi.Schema(
                title="Poll title",
                type=openapi.TYPE_STRING,
            ),
            "closes_at": openapi.Schema(
                title="Poll close date-time",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATETIME
            ),
            "category": openapi.Schema(
                title="Discourse category id",
                type=openapi.TYPE_INTEGER
            ),
        },
        'required': ["title"],
    }

    @staticmethod
    def start(process_state: ProcessState, querydict) -> None:
        logger.info(querydict)

        url = f"{discourse_server_url}/posts.json"
        closes_at = querydict.get("closes_at", "2021-02-17T17:19:00.000Z")
        raw = f"""
[poll type=regular results=always chartType=bar close={closes_at}]
# {querydict.get("title", "Select an option")}
* one
* two
* three
* four
[/poll]
        """
        payload = {
            "raw": raw,
            "title": querydict.get("title"),
            "category": querydict.get("category", 8)
        }

        headers = {
            'Api-Key': system_api_key, 'Api-Username': 'system'}
        logger.info(payload)
        logger.info(url)
        resp = requests.post(url, data=payload, headers=headers)
        if not resp.ok:
            logger.error(
                f"Error: {resp.status_code} {resp.text}")
            process_state.set_errors({'text': resp.text or "unknown error"})
            process_state.set_status(ProcessStatus.COMPLETED)
            return

        response = resp.json()
        logger.info(response)
        if response.get('errors'):
            process_state.set_errors(response['errors'])
            process_state.set_status(ProcessStatus.COMPLETED)
        else:
            poll_url = f"{discourse_server_url}/t/{response.get('topic_slug')}/{response.get('topic_id')}"
            logger.info(f"Poll created at {poll_url}")

            process_state.set_data_value(
                'post_number', response.get('post_number'))
            process_state.set_data_value('topic_id', response.get('topic_id'))
            process_state.set_data_value(
                'topic_slug', response.get('topic_slug'))
            process_state.set_data_value('poll_url', poll_url)
            process_state.set_status(ProcessStatus.PENDING)

    @staticmethod
    def handle_webhook(process_state: ProcessState, request) -> None:
        try:
            body = json.loads(request.body)
        except ValueError:
            logger.error("unable to decode webhook body")
        # logger.info(body)

    @staticmethod
    def cancel(process_state: ProcessState) -> None:
        # cancel poll
        pass
