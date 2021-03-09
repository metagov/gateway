import json
import logging

import requests
from django.db import models
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseNotFound)
from drf_yasg import openapi
from metagov.core.plugin_models import (GovernanceProcessProvider,
                                        ProcessState, ProcessStatus,
                                        load_settings)

logger = logging.getLogger('django')

settings = load_settings("loomio")
loomio_api_key = settings['loomio_api_key']

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
        "details": {
            "type": "string"
        },
        "closing_at": {
            "type": "string",
            "format": "date"
        }
    },
    "required": [
        "title",
        "options",
        "closing_at"
    ]
}


class Loomio(GovernanceProcessProvider):
    slug = 'loomio'
    input_schema = input_schema

    @staticmethod
    def start(process_state: ProcessState, parameters) -> None:
        url = "https://www.loomio.org/api/b1/polls"
        loomio_data = {
            'title': parameters['title'],
            'poll_type': 'proposal',
            'options[]': parameters['options'],
            'details': parameters.get('details', 'Created by Metagov'),
            'closing_at': parameters['closing_at'],
            'api_key': loomio_api_key
        }

        resp = requests.post(url, loomio_data)
        if not resp.ok:
            logger.error(
                f"Error creating Loomio poll: {resp.status_code} {resp.text}")
            process_state.set_errors({'text': resp.text or "unknown error"})
            process_state.set_status(ProcessStatus.COMPLETED)
            return

        response = resp.json()

        if response.get('errors'):
            process_state.set_errors(response['errors'])
            process_state.set_status(ProcessStatus.COMPLETED)
        else:
            poll_key = response.get('polls')[0].get('key')
            poll_url = 'https://www.loomio.org/p/' + poll_key
            process_state.set_data_value('poll_key', poll_key)
            process_state.set_data_value('poll_url', poll_url)
            process_state.set_status(ProcessStatus.PENDING)

    @staticmethod
    def handle_webhook(process_state: ProcessState, request) -> None:
        poll_key = process_state.get_data_value('poll_key')
        poll_url = process_state.get_data_value('poll_url')
        if not poll_key or not poll_url:
            return

        try:
            body = json.loads(request.body)
        except ValueError:
            logger.error("unable to decode webhook body")

        kind = body.get('kind')
        url = body.get('url')
        if url is None:
            return
        if not url.startswith(poll_url):
            return

        logger.info(f"Processing event '{kind}' for poll {url}")
        if kind == "poll_closed_by_user" or kind == "poll_expired":
            logger.info(f"Loomio poll closed. Fetching poll result...")
            url = f"https://www.loomio.org/api/b1/polls/{poll_key}?api_key={loomio_api_key}"
            resp = requests.get(url)
            if not resp.ok:
                logger.error(
                    f"Error fetching poll outcome: {resp.status_code} {resp.text}")
                process_state.set_errors(
                    {'text': resp.text or "unknown errors"})
                process_state.set_status(ProcessStatus.COMPLETED)
            response = resp.json()
            if response.get('errors'):
                process_state.set_errors(response['errors'])
                process_state.set_status(ProcessStatus.COMPLETED)
            else:
                outcome = response.get('polls')[0].get('stance_data')
                process_state.set_outcome(outcome)
                process_state.set_status(ProcessStatus.COMPLETED)

    @staticmethod
    def cancel(process_state: ProcessState) -> None:
        # cancel poll
        pass
