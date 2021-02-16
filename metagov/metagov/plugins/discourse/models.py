import json
import logging

import requests
from drf_yasg import openapi
from metagov.core.plugin_models import (GovernanceProcessProvider,
                                        ProcessState, ProcessStatus,
                                        webhook_listener, load_settings)

logger = logging.getLogger('django')

settings = load_settings("discourse")

@webhook_listener("discourse", "listen to events on discourse")
def process_webhook(request):
    instance = request.headers.get('X-Discourse-Instance')
    event_id = request.headers.get('X-Discourse-Event-Id')
    event_type = request.headers.get('X-Discourse-Event-Type')
    event = request.headers.get('X-Discourse-Event')
    logger.info(f"Received event {event} from {instance}")
    # create event, notify core


class DiscoursePoll(GovernanceProcessProvider):
    slug = 'discourse-poll'
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

        url = f"{settings['discourse_url']}/posts.json"
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

        headers = {'Api-Key': settings['discourse_api_key'], 'Api-Username': 'system'}
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
            poll_url = f"{settings['discourse_url']}/t/{response.get('topic_slug')}/{response.get('topic_id')}"
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
