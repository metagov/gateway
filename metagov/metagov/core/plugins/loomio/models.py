from django.db import models
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from metagov.core.plugins import GovernanceProcessProvider, GovernanceProcessStatus
from metagov.core.plugins.loomio import conf
import json
import requests
import logging

logger = logging.getLogger('django')

"""
job_state: for storing any state you need to persist in the database
"""


class Loomio(GovernanceProcessProvider):
    slug = 'loomio'

    @staticmethod
    def start(job_state, querydict):
        url = "https://www.loomio.org/api/b1/polls"
        loomio_data = {
            'title': querydict.get('title', 'agree or disagree'),
            'poll_type': 'proposal',
            'options[]': ['agree', 'disagree'],
            'details': 'created by metagov',
            'closing_at': '2021-02-03',
            'api_key': conf.LOOMIO_API_KEY
        }
        resp = requests.post(url, loomio_data)
        response = resp.json()
        poll_key = response.get('polls')[0].get('key')
        poll_url = 'https://www.loomio.org/p/' + poll_key
        # store these in state so they can be accessed later
        job_state.set('poll_key', poll_key)
        job_state.set('poll_url', poll_url)

        result = {
            'poll_url': poll_url
        }
        return result

    @staticmethod
    def handle_webhook(job_state, querydict):
        kind = querydict.get('kind')
        url = querydict.get('url')
        if not url:
            return
        if not url.startswith(job_state.get('poll_url')):
            return

        logger.info(f"Processing event {kind} for poll {url}")
        job_state.set('latest_event', kind)
        # FIXME if poll closed, get outcome and update job state...

    @staticmethod
    def check(job_state):
        # for polling. check status, update state
        pass

    @staticmethod
    def get_status(job_state):
        # given currently stored job state, what is the status?
        if job_state.get('outcome'):
            return GovernanceProcessStatus.COMPLETED
        if job_state.get('poll_key'):
            return GovernanceProcessStatus.PENDING
        return GovernanceProcessStatus.CREATED
