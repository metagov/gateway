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
        resp = requests.post(settings.DRIVER_ACTION_ENDPOINT, data=serialized)
        if not resp.ok:
            print(f"Error sending event to driver: {resp.status_code} {resp.reason}")


class ProcessStatus(Enum):
    CREATED = "created"
    PENDING = "pending"
    COMPLETED = "completed"


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
    state = models.OneToOneField(DataStore, models.CASCADE, help_text="Datastore to persist any state", null=True)
    data = models.JSONField(default=dict, blank=True, help_text="Data to serialize and send back to driver")
    errors = models.JSONField(default=dict, blank=True, help_text="Errors to serialize and send back to driver")
    outcome = models.JSONField(default=dict, blank=True, help_text="Outcome to serialize and send back to driver")
    input_schema = {}

    def __str__(self):
        return f"{self.plugin.name}.{self.name} for '{self.plugin.community.name}' ({self.pk}, {self.status})"

    def save(self, *args, **kwargs):
        """Save the process. Has a pre-save hook that will send the serialized process to the Driver
        if the ``status`` was changed to ``completed``."""
        if not self.pk:
            self.state = DataStore.objects.create()
        super(GovernanceProcess, self).save(*args, **kwargs)

    def start(self, parameters):
        """Start the governance process and return immediately. (REQUIRED).

        Most implementations of this function will:
        - Make a request to start a governance process in an external system

        - Store some private state in ``self.state``

        - If process was started successfully, set ``self.status`` to ``PENDING`` and put data that should be returned to the caller into ``self.data``.

        - If process failed to start, set ``self.status`` to ``COMPLETED`` and put errors into ``self.errors``.

        - Call ``self.save()`` to persist changes."""
        pass

    def close(self):
        """Close the governance process and update the ``outcome``. (OPTIONAL)

        Most implementations of this function will:
        - Make a request to close the governance process in an external system

        - Store some private state in ``self.state``

        - If process was closed successfully, set ``self.status`` to ``COMPLETED`` and put the outcome into ``self.outcome``.

        - If process failed, set ``self.status`` to ``COMPLETED`` and put errors into ``self.errors``.

        - Call ``self.save()`` to persist changes.
        """
        pass

    def poll(self):
        """Poll the process, and possibly update the status. (OPTIONAL)"""
        pass

    def receive_webhook(self, request):
        """Receive an incoming webhook from an external system. (OPTIONAL)

        Most implementations of this function will:
        - Check if the webhook request pertains to this process instance.

        - Store some private state in ``self.state``.

        - If the webhook request indicates that the process has ended, update ``self.status`` and ``self.outcome`` or ``self.errors``.

        - Call ``self.save()`` to persist changes."""
        pass


@receiver(pre_save, sender=GovernanceProcess, dispatch_uid="process_saved")
def notify_process_completed(sender, instance, **kwargs):
    """Pre-save receiver to notify caller that the governance processes has completed"""

    def notify_completed(process):
        from metagov.core.serializers import GovernanceProcessSerializer

        if not process.callback_url:
            logger.info("No callback url")
            return
        serializer = GovernanceProcessSerializer(process)
        logger.info(f"Posting completed process outcome to {process.callback_url}")
        logger.info(serializer.data)
        resp = requests.post(process.callback_url, json=serializer.data)
        if not resp.ok:
            logger.error(f"Error posting outcome to callback url: {resp.status_code} {resp.text}")

    try:
        obj = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        # instance is new
        if instance.status == ProcessStatus.COMPLETED.value:
            notify_completed(instance)
    else:
        if not obj.status == instance.status:
            logger.info(f"Status changed: {obj.status} -> {instance.status}")
            if instance.status == ProcessStatus.COMPLETED.value:
                notify_completed(instance)
