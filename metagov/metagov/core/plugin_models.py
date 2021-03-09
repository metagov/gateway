from __future__ import annotations

import os
import sys
import abc
import jsonpickle
import requests
import jsonschema
from django.conf import settings
from enum import Enum
from typing import TYPE_CHECKING, Any

import environ
import yaml

if TYPE_CHECKING:
    from metagov.core.models import GovernanceProcess

# Based on http://martyalchin.com/2008/jan/10/simple-plugin-framework/
# Plugins SHOULD import this file
# Core SHOULD import this file
# Plugins SHOULD NOT import other files from core


env = environ.Env()


def load_settings(plugin_dirname):
    path = os.path.join(sys.path[0], 'metagov',
                        'plugins', plugin_dirname, 'settings.yml')
    with open(path) as file:
        settings_config = yaml.load(file, Loader=yaml.FullLoader)
        settings = dict()
        for key in settings_config.keys():
            # Look for values in global env for now
            # TODO replace this with namespaced settings
            # that can be exposed in the UI optionally
            value = env(key.upper()) or key.default
            settings[key] = value
        return settings


class SaferDraft7Validator(jsonschema.Draft7Validator):
    META_SCHEMA = {**jsonschema.Draft7Validator.META_SCHEMA,
                   "additionalProperties": False}


class RegisteredFunction:
    def __init__(self, slug, function, description, input_schema, output_schema):
        self.slug = slug
        self.function = function
        self.description = description
        self.input_schema = input_schema
        self.output_schema = output_schema


class FunctionRegistry(object):
    def __init__(self):
        self.registry = dict()

    def get(self, slug):
        return self.registry.get(slug)

    def add(self, function, slug, description, input_schema=None, output_schema=None):
        if slug in self.registry:
            raise Exception(f"Duplicate function slug '{slug}'")
        if input_schema:
            SaferDraft7Validator.check_schema(input_schema)
        if output_schema:
            SaferDraft7Validator.check_schema(output_schema)
        self.registry[slug] = RegisteredFunction(
            slug=slug,
            function=function,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema
        )


resource_retrieval_registry = FunctionRegistry()
action_function_registry = FunctionRegistry()


def register_resource(slug, description, input_schema=None, output_schema=None):
    """
    Decorator for resource retrieval functions
    """
    def decorate(func):
        resource_retrieval_registry.add(
            func, slug, description, input_schema, output_schema)
        return func
    return decorate


def register_action(slug, description, input_schema, output_schema):
    """
    Decorator for platform action functions
    """
    def decorate(func):
        action_function_registry.add(
            func, slug, description, input_schema, output_schema)
        return func
    return decorate


class BaseUser(abc.ABC):
    username: str = NotImplemented

    def __init__(self, username: str):
        self.username = username


class BaseCommunity(abc.ABC):
    # human-readable name of the community
    name: str = NotImplemented
    # machine-readable unique id of the community
    unique_id: str = NotImplemented
    # name of the platform
    platform: str = NotImplemented


class PlatformEvent:
    """
    Event that has occurred on a platform.
    """

    def __init__(self, community, event_type, initiator, timestamp, data):
        self.community = community
        self.event_type = event_type
        self.initiator = initiator
        self.timestamp = timestamp
        self.data = data  # this can be validated based on a schema

    def toJSON(self):
        return jsonpickle.encode(self, unpicklable=False)

    def send(self):
        """
        Send event to registered Driver endpoint
        """
        # TODO log to special file or db
        serialized = self.toJSON()
        resp = requests.post(settings.DRIVER_ACTION_ENDPOINT, data=serialized)
        if not resp.ok:
            print(
                f"Error posting action to driver: {resp.status_code} {resp.reason}")


class ListenerRegistry(object):
    def __init__(self):
        self.registry = dict()

    def get(self, name):
        return self.registry.get(name)

    def add(self, name, description, function):
        if name in self.registry:
            raise ValueError(f"Duplicate listener name '{name}'")

        self.registry[name] = {
            'description': description,
            'function': function
        }

listener_registry = FunctionRegistry()

def register_listener(slug, description):
    """
    Decorator for webhook listener functions
    """
    def decorate(func):
        listener_registry.add(func, slug, description)
        return func
    return decorate

class PluginMount(type):
    def __init__(cls, name, bases, attrs):
        if not hasattr(cls, 'plugins'):
            # This branch only executes when processing the mount point itself.
            # So, since this is a new plugin type, not an implementation, this
            # class shouldn't be registered as a plugin. Instead, it sets up a
            # dict where plugins can be registered later.
            cls.plugins = dict()
        else:
            # This must be a plugin implementation, which should be registered.
            cls.plugins[cls.slug] = cls


class GovernanceProcessProvider(metaclass=PluginMount):
    """
    Mount point for plugins which refer to governance processes that can be performed.
    Plugins implementing this reference should provide the following static functions:
    ========  ========================================================
    start     kick off the governance process
    cancel    cancel the governance process
    close     close the governance process
    ========  ========================================================
    """
    input_schema = {}

    @staticmethod
    def start(process_state, parameters) -> None:
        # start process, update state
        # returns result
        pass

    @staticmethod
    def close(process_state, parameters) -> None:
        # close process, update state
        # returns outcome
        pass

    @staticmethod
    def cancel(process_state) -> None:
        # cancel job, update state
        pass

    @staticmethod
    def check(process_state) -> None:
        # check job status, update state if necessary (used for polling)
        # returns outcome
        pass

    @staticmethod
    def handle_webhook(process_state, request) -> None:
        # process data from webhook endpoint; update state if necessary
        pass

class ProcessStatus(Enum):
    CREATED = 'created'
    PENDING = 'pending'
    COMPLETED = 'completed'


class ProcessState:
    """
    Wrapper class for GovernanceProcess model. This is provided to plugins, so
    they can access and modify job state, but not the Model directly.
    """

    def __init__(self, model: GovernanceProcess) -> None:
        self.__model = model

    def get_status(self) -> str:
        return self.status

    def set_status(self, status: ProcessStatus) -> None:
        if not isinstance(status, ProcessStatus):
            raise ValueError(f"Status must be an instance of ProcessStatus")
        self.__model.status = status.value
        self.__model.save()

    def get_data_value(self, key: str) -> Any:
        return self.__model.data.get(key, None)

    def set_data_value(self, key: str, value: Any) -> None:
        self.__model.data[key] = value
        self.__model.save()

    def get_errors(self) -> Any:
        return self.__model.errors

    def set_errors(self, obj: Any) -> None:
        self.__model.errors = obj
        self.__model.save()

    def get_outcome(self) -> Any:
        return self.__model.outcome

    def set_outcome(self, obj: Any) -> None:
        self.__model.outcome = obj
        self.__model.save()
