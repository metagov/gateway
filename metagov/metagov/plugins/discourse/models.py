import json
import logging
import jsonpickle
import requests
import time
import hmac
import hashlib
import base64
from drf_yasg import openapi
import metagov.plugins.discourse.schemas as Schemas
from metagov.core.plugin_models import (GovernanceProcessProvider,
                                        ProcessState, ProcessStatus,
                                        load_settings,
                                        register_listener,
                                        BaseCommunity,
                                        register_resource,
                                        send_platform_event,
                                        register_action)


logger = logging.getLogger('django')

settings = load_settings("discourse")

discourse_server_url = settings['discourse_url']
system_api_key = settings['discourse_api_key']
discourse_webhook_secret = settings['discourse_webhook_secret']


def construct_post_url(post):
    return f"{discourse_server_url}/t/{post['topic_slug']}/{post['topic_id']}/{post['post_number']}?u={post['username']}"


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


def discourse_post_request(route, payload, username):
    headers = {
        'Content-Type': 'application/json',
        'Api-Username': username,
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
    slug="discourse.create-post",
    description="Create a new post on discourse",
    input_schema=Schemas.create_post_parameters,
    output_schema=Schemas.create_post_response
)
def create_post(parameters, initiator):
    payload = {'raw': parameters['raw'], 'topic_id': parameters['topic_id']}
    username = initiator or 'system'
    post = discourse_post_request("posts.json", payload, username)
    return {'url': construct_post_url(post), 'id': post['id']}


@register_action(
    slug="discourse.delete-post",
    description="Delete a post on discourse",
    input_schema=Schemas.delete_post_parameters,
    output_schema=None
)
def delete_post(parameters, initiator):
    headers = {
        'Api-Username': 'system',
        'Api-Key': system_api_key
    }
    resp = requests.delete(
        f"{discourse_server_url}/posts/{parameters['id']}", headers=headers)
    if not resp.ok:
        logger.error(f"{resp.status_code} {resp.reason}")
        raise ValueError(resp.text)
    return {}


@register_action(
    slug="discourse.lock-post",
    description="Lock or unlock a post on discourse",
    input_schema=Schemas.lock_post_parameters,
    output_schema=Schemas.lock_post_response,
)
def lock_post(parameters, initiator):
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Api-Username': 'system',
        'Api-Key': system_api_key
    }
    data = {'locked': json.dumps(parameters['locked'])}
    resp = requests.put(
        f"{discourse_server_url}/posts/{parameters['id']}/locked", headers=headers, data=data)
    if not resp.ok:
        logger.error(f"{resp.status_code} {resp.reason}")
        raise ValueError(resp.text)
    return resp.json()


"""
LISTENERS
"""


def validate_request_signature(request):
    event_signature = request.headers['X-Discourse-Event-Signature']
    key = bytes(discourse_webhook_secret, 'utf-8')
    string_signature = hmac.new(key, request.body, hashlib.sha256).hexdigest()
    expected_signature = f"sha256={string_signature}"
    if not hmac.compare_digest(event_signature, expected_signature):
        raise Exception('Invalid signature header')

    instance = request.headers['X-Discourse-Instance']
    if instance != discourse_server_url:
        raise Exception("Unexpected X-Discourse-Instance")


@register_listener("discourse", "receive events from Discourse")
def listener(request):
    validate_request_signature(request)
    event = request.headers.get('X-Discourse-Event')
    body = json.loads(request.body)
    logger.info(f"Received event '{event}' from Discourse")

    if event == "post_created":
        post = body.get('post')
        data = {'raw': post['raw'],
                'topic_id': post['topic_id'],
                'id': post['id'],
                'url': construct_post_url(post)}
        initiator = {'user_id': post['username'],
                     'provider': 'discourse'}
        send_platform_event(
            event_type="post_created",
            community=community,
            initiator=initiator,
            data=data
        )


"""
RESOURCE RETRIEVALS
"""


@register_resource('discourse.badges', 'Discourse badges for a given user')
def get_discourse_badges(parameters):
    raise NotImplementedError


"""
GOVERNANCE PROCESSES
"""


class DiscoursePoll(GovernanceProcessProvider):
    slug = 'discourse-poll'

    input_schema = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string"
            },
            "options": {
                "type": "array",
                "items": {
                    "type": "string"
                }
            },
            "category": {
                "type": "integer"
            },
            "closing_at": {
                "type": "string",
                "format": "date"
            }
        },
        "required": [
            "title",
            "closing_at"
        ]
    }

    @staticmethod
    def start(process_state: ProcessState, parameters) -> None:
        url = f"{discourse_server_url}/posts.json"
        closes_at = parameters["closing_at"]
        options = "".join([f"* {opt}\n" for opt in parameters['options']])
        raw = f"""
[poll type=regular results=always chartType=bar close={closes_at}]
# {parameters["title"]}
{options}
[/poll]
        """
        payload = {
            "raw": raw,
            "title": parameters.get("title"),
            "category": parameters.get("category", 8)
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
