from django.db import models
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from metagov.core.plugin_models import GovernanceProcessProvider, GovernanceProcessStatus
from metagov.plugins.loomio import conf
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
        job_state.set('poll_key', poll_key)
        job_state.set('poll_url', poll_url)
        return {'poll_url': poll_url}

    @staticmethod
    def handle_webhook(job_state, querydict):
        kind = querydict.get('kind')
        url = querydict.get('url')
        if url is None:
            return
        if not url.startswith(job_state.get('poll_url')):
            return

        logger.info(f"Processing event '{kind}' for poll {url}")
        if kind == "poll_closed_by_user":
            # FIXME get outcome from Loomio, store in job state
            job_state.set('outcome', 'unknown')

    @staticmethod
    def cancel(job_state):
        # cancel poll
        pass

    @staticmethod
    def close(job_state):
        # close poll, return outcome
        pass

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

    @staticmethod
    def get_outcome(job_state):
        # return outcome IF COMPLETED
        return job_state.get('outcome')
