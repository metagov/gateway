import json
import logging

import requests
from django.db import models
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseNotFound)
from drf_yasg import openapi
from metagov.core.plugin_models import (GovernanceProcessProvider,
                                        ProcessState, ProcessStatus)
from metagov.plugins.loomio import conf

logger = logging.getLogger('django')

"""
process_state: for storing any state you need to persist in the database
"""

input_schema = {
    'properties': {
        "title": openapi.Schema(
            title="Poll Title",
            type=openapi.TYPE_STRING,
        ),
        "closes_at": openapi.Schema(
            title="Poll close date",
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_DATE
        ),
    },
    'required': ["title", "closes_at"],
}


class Loomio(GovernanceProcessProvider):
    slug = 'loomio'
    input_schema = input_schema

    @staticmethod
    def start(process_state: ProcessState, querydict) -> None:
        url = "https://www.loomio.org/api/b1/polls"
        loomio_data = {
            'title': querydict.get('title', 'agree or disagree'),
            'poll_type': 'proposal',
            'options[]': querydict.getlist('options', ['agree', 'disagree']),
            'details': querydict.get('details', 'created by metagov'),
            'closing_at': querydict.get('closing_at', '2021-04-03'),
            'api_key': conf.LOOMIO_API_KEY
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
            return
        else:
            poll_key = response.get('polls')[0].get('key')
            poll_url = 'https://www.loomio.org/p/' + poll_key
            process_state.set_data_value('poll_key', poll_key)
            process_state.set_data_value('poll_url', poll_url)

    @staticmethod
    def handle_webhook(process_state: ProcessState, querydict) -> None:
        poll_key = process_state.get_data_value('poll_key')
        poll_url = process_state.get_data_value('poll_url')
        if not poll_key or not poll_url:
            return

        kind = querydict.get('kind')
        url = querydict.get('url')
        if url is None:
            return
        if not url.startswith(poll_url):
            return

        logger.info(f"Processing event '{kind}' for poll {url}")
        if kind == "poll_closed_by_user" or kind == "poll_expired":
            logger.info(f"Loomio poll closed. Fetching poll result...")
            url = f"https://www.loomio.org/api/b1/polls/{poll_key}?api_key={conf.LOOMIO_API_KEY}"
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
