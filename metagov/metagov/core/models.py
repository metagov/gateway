import json
import logging
import time
import jsonpickle
from enum import Enum

import jsonpickle
import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi

logger = logging.getLogger("django")


class Community(models.Model):
    name = models.CharField(max_length=50, primary_key=True)
    readable_name = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.readable_name} ({self.name})"


class DataStore(models.Model):
    datastore = models.JSONField(default=dict)

    def get(self, key):
        value = self.datastore.get(key)
        if value is not None:
            return jsonpickle.decode(value)
        return value

    def set(self, key, value):
        self.datastore[key] = jsonpickle.encode(value)
        self.save()
        return True

    def remove(self, key):
        res = self.datastore.pop(key, None)
        self.save()
        if not res:
            return False
        return True


class PluginManager(models.Manager):
    def get_queryset(self):
        qs = super(PluginManager, self).get_queryset()
        if self.model._meta.proxy:
            # this is a proxy model, so only return plugins of this proxy type
            return qs.filter(name=self.model.name)
        return qs


class Plugin(models.Model):
    """Represents an instance of an activated plugin."""

    name = models.CharField(max_length=30, blank=True, help_text="Name of the plugin")
    community = models.ForeignKey(
        Community, models.CASCADE, related_name="plugins", help_text="Community that this plugin instance belongs to"
    )
    config = models.JSONField(default=dict, null=True, blank=True, help_text="Configuration for this plugin instance")
    state = models.OneToOneField(DataStore, models.CASCADE, help_text="Datastore to persist any state", null=True)
    config_schema = {}  # can be overridden to set jsonschema of config

    objects = PluginManager()

    class Meta:
        unique_together = ["name", "community"]

    def __str__(self):
        return f"{self.name} for {self.community.name}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.state = DataStore.objects.create()
            self.initialize()
        super(Plugin, self).save(*args, **kwargs)

    def initialize(self):
        """Initialize the plugin. Invoked once, when the plugin instance is created."""
        pass

    def receive_webhook(self, request):
        """Receive webhook event"""
        pass

    def send_event_to_driver(self, event_type: str, data: dict, initiator: dict):
        """Send an event to the driver"""
        if not settings.DRIVER_EVENT_RECEIVER_URL:
            return
        event = {
            "community": self.community.name,
            "source": self.name,
            "event_type": event_type,
            "timestamp": str(time.time()),
            "data": data,
            "initiator": initiator,
        }
        serialized = jsonpickle.encode(event, unpicklable=False)
        logger.info("Sending event to Driver: " + serialized)
        resp = requests.post(settings.DRIVER_EVENT_RECEIVER_URL, data=serialized)
        if not resp.ok:
            logger.error(f"Error sending event to driver: {resp.status_code} {resp.reason}")


class ProcessStatus(Enum):
    CREATED = "created"
    PENDING = "pending"
    COMPLETED = "completed"

class GovernanceProcessManager(models.Manager):
    def get_queryset(self):
        qs = super(GovernanceProcessManager, self).get_queryset()
        if self.model._meta.proxy:
            # this is a proxy model, so only return processes of this proxy type
            return qs.filter(name=self.model.name, plugin__name=self.model.plugin_name)
        return qs

class GovernanceProcess(models.Model):
    """Represents an instance of a governance process."""

    name = models.CharField(max_length=30)
    callback_url = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(
        max_length=15, choices=[(s.value, s.name) for s in ProcessStatus], default=ProcessStatus.CREATED.value
    )
    plugin = models.ForeignKey(
        Plugin, models.CASCADE, related_name="plugin", help_text="Plugin instance that this process belongs to"
    )
    state = models.OneToOneField(DataStore, models.CASCADE, help_text="Datastore to persist any internal state", null=True)
    errors = models.JSONField(default=dict, blank=True, help_text="Errors to serialize and send back to driver")
    outcome = models.JSONField(default=dict, blank=True, help_text="Outcome to serialize and send back to driver")
    input_schema = {}

    objects = GovernanceProcessManager()

    def __str__(self):
        return f"{self.plugin.name}.{self.name} for '{self.plugin.community.name}' ({self.pk}, {self.status})"

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        # save status when model is loaded from database, so we can tell when it changes
        loaded_values = dict(zip(field_names, values))
        instance._loaded_status = loaded_values["status"]
        return instance

    def save(self, *args, **kwargs):
        """Saves the process. If the ``status`` was changed to ``completed`` and there is a ``callback_url`` defined
        for this process, it will post the serialized process to the callback URL. Do not override this function."""
        if not self.pk:
            self.state = DataStore.objects.create()

        if not self._state.adding:
            if self.status != self._loaded_status:
                logger.info(f"[{self}] {self._loaded_status} -> {self.status}")
                if self.status == ProcessStatus.COMPLETED.value:
                    notify_process_completed(self)
        elif not hasattr(self, "_loaded_status"):
            self._loaded_status = self.status
        super(GovernanceProcess, self).save(*args, **kwargs)

    def start(self, parameters):
        """(REQUIRED) Start the governance process.

        Most implementations of this function will:

        - Make a request to start a governance process in an external system

        - Store any data in ``outcome`` that should be returned to the Driver. For example, the URL for a voting process in another system.

        - Store any internal state in ``state``

        - If process was started successfully, set ``status`` to ``pending``.

        - If process failed to start, raise an exception of type ``PluginErrorInternal``.

        - Call ``self.save()`` to persist changes."""
        pass

    def close(self):
        """(OPTIONAL) Close the governance process.

        Most implementations of this function will:

        - Make a request to close the governance process in an external system

        - If process was closed successfully, set ``status`` to ``completed`` and put the outcome into ``self.outcome``.

        - If the process failed to close, set ``errors`` or raise an exception of type ``PluginErrorInternal``.

        - Call ``self.save()`` to persist changes.
        """
        raise NotImplementedError

    def check_status(self):
        """(OPTIONAL) Check the status of the process. May be called repeatedly to poll for changes.

        Most implementations of this function will:

        - Make a request to get the current status from an external system

        - Update ``state``, ``status`` (if process closed), ``outcome``, and/or ``errors`` as needed.

        - Call ``self.save()`` to persist changes."""
        pass

    def receive_webhook(self, request):
        """(OPTIONAL) Receive an incoming webhook from an external system.

        Most implementations of this function will:

        - Check if the webhook request pertains to this process instance.

        - Update ``state``, ``status`` (if process closed), ``outcome``, and/or ``errors`` as needed.

        - Call ``self.save()`` to persist changes."""
        pass


def notify_process_completed(process: GovernanceProcess):
    """Notify the Driver that this GovernanceProess has completed."""
    assert process.status == ProcessStatus.COMPLETED.value
    if not process.callback_url:
        return
    logger.info(f"Posting completed process outcome to '{process.callback_url}'")
    from metagov.core.serializers import GovernanceProcessSerializer

    serializer = GovernanceProcessSerializer(process)
    logger.info(serializer.data)
    resp = requests.post(process.callback_url, json=serializer.data)
    if not resp.ok:
        logger.error(f"Error posting outcome to callback url: {resp.status_code} {resp.text}")
