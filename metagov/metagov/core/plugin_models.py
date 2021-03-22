from __future__ import annotations

import os
import sys
import abc
import jsonpickle
import requests
import jsonschema
import time
import logging
from django.conf import settings
from enum import Enum
from typing import TYPE_CHECKING, Any
from constance import config

import environ
import yaml

logger = logging.getLogger('django')


# Based on http://martyalchin.com/2008/jan/10/simple-plugin-framework/
# Plugins SHOULD import this file
# Core SHOULD import this file
# Plugins SHOULD NOT import other files from core



class BaseCommunity(abc.ABC):
    # human-readable name of the community
    name: str = NotImplemented
    # machine-readable unique id of the community
    unique_id: str = NotImplemented
    # name of the platform
    platform: str = NotImplemented


class PlatformEvent:
    def __init__(self, community, event_type, initiator, timestamp, data):
        self.community = community
        self.event_type = event_type
        self.initiator = initiator
        self.timestamp = timestamp
        self.data = data

    def toJSON(self):
        return jsonpickle.encode(self, unpicklable=False)


def send_platform_event(event_type: str, community: BaseCommunity, initiator, data):
    event = PlatformEvent(
        community=community,
        event_type=event_type,
        initiator=initiator,
        timestamp=str(time.time()),
        data=data
    )
    serialized = event.toJSON()
    logger.info("Sending event to Driver: " + serialized)
    resp = requests.post(settings.DRIVER_ACTION_ENDPOINT, data=serialized)
    if not resp.ok:
        print(
            f"Error sending event to driver: {resp.status_code} {resp.reason}")

class ProcessStatus(Enum):
    CREATED = 'created'
    PENDING = 'pending'
    COMPLETED = 'completed'

