import json
import logging

import metagov.core.plugin_decorators as Registry
import requests
from django.db import models
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseNotFound)
from drf_yasg import openapi
from metagov.core.models import GovernanceProcess, Plugin, ProcessStatus

logger = logging.getLogger('django')


@Registry.plugin
class Loomio(Plugin):
    name = "loomio"
    config_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "api_key": {
                "type": "string"
            },
            "webhook_slug": {
                "type": "string"
            }
        },
        "required": [
            "api_key"
        ]
    }

    class Meta:
        proxy = True


@Registry.governance_process
class LoomioPoll(GovernanceProcess):
    name = 'poll'
    plugin_name = 'loomio'
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

    class Meta:
        proxy = True

    def start(self, parameters) -> None:
        url = "https://www.loomio.org/api/b1/polls"
        loomio_data = {
            'title': parameters['title'],
            'poll_type': 'proposal',
            'options[]': parameters['options'],
            'details': parameters.get('details', 'Created by Metagov'),
            'closing_at': parameters['closing_at'],
            'api_key': self.plugin.config['api_key']
        }

        resp = requests.post(url, loomio_data)
        if not resp.ok:
            logger.error(
                f"Error creating Loomio poll: {resp.status_code} {resp.text}")
            self.errors = {'text': resp.text or "unknown error"}
            self.status = ProcessStatus.COMPLETED.value
            self.save()
            return

        response = resp.json()

        if response.get('errors'):
            self.errors = response['errors']
            self.status = ProcessStatus.COMPLETED.value
        else:
            poll_key = response.get('polls')[0].get('key')
            poll_url = f"https://www.loomio.org/p/{poll_key}"
            self.state.set('poll_key', poll_key)
            self.state.set('poll_url', poll_url)
            self.data = {'poll_url': poll_url}
            self.status = ProcessStatus.PENDING.value

        self.save()

    def receive_webhook(self, request):
        poll_key = self.state.get('poll_key')
        poll_url = self.state.get('poll_url')
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
            url = f"https://www.loomio.org/api/b1/polls/{poll_key}?api_key={self.plugin.config['api_key']}"
            resp = requests.get(url)
            if not resp.ok:
                logger.error(
                    f"Error fetching poll outcome: {resp.status_code} {resp.text}")
                self.errors = {'text': resp.text or "unknown error"}
                self.status = ProcessStatus.COMPLETED.value

            response = resp.json()
            if response.get('errors'):
                self.errors = response['errors']
                self.status = ProcessStatus.COMPLETED.value
            else:
                outcome = response.get('polls')[0].get('stance_data')
                self.outcome = outcome
                self.status = ProcessStatus.COMPLETED.value

            self.save()
