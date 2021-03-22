import json
import logging
import time
from enum import Enum

import jsonpickle
import requests
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi

logger = logging.getLogger('django')


class Community(models.Model):
    name = models.CharField(max_length=30, primary_key=True)
    readable_name = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.readable_name} ({self.name})"


class DataStore(models.Model):
    datastore = models.JSONField(default=dict)

    def get(self, key):
        return self.datastore.get(key, None)

    def set(self, key, value):
        self.datastore[key] = value
        self.save()
        return True

    def remove(self, key):
        res = self.datastore.pop(key, None)
        self.save()
        if not res:
            return False
        return True


class Plugin(models.Model):
    name = models.CharField(max_length=30, blank=True,
                            help_text="Name of the plugin")
    community = models.ForeignKey(Community, models.CASCADE, related_name='plugins',
                                  help_text="Community that this plugin instance belongs to")
    config = models.JSONField(default=dict, null=True, blank=True,
                              help_text="Configuration for this plugin instance")
    state = models.OneToOneField(DataStore,
                                 models.CASCADE,
                                 help_text="Datastore to persist any state",
                                 null=True
                                 )
    config_schema = {}  # can be overridden to set jsonschema of config

    class Meta:
        unique_together = ['name', 'community']

    def __str__(self):
        return f"{self.name} for {self.community.name}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.state = DataStore.objects.create()
            self.initialize()
        super(Plugin, self).save(*args, **kwargs)

    def initialize(self):
        pass

    def receive_webhook(self, request):
        pass

    def send_event_to_driver(self, event_type: str, data: dict, initiator: dict):
        event = {
            'community': self.community.name,
            'source': self.name,
            'event_type': event_type,
            'timestamp': str(time.time()),
            'data': data,
            'initiator': initiator
        }
        serialized = jsonpickle.encode(self, unpicklable=False)
        logger.info("Sending event to Driver: " + serialized)
        resp = requests.post(settings.DRIVER_ACTION_ENDPOINT, data=serialized)
        if not resp.ok:
            print(
                f"Error sending event to driver: {resp.status_code} {resp.reason}")


class ProcessStatus(Enum):
    CREATED = 'created'
    PENDING = 'pending'
    COMPLETED = 'completed'


class AsyncProcess(models.Model):
    """
    Model representing an instance of a governance process. There can be multiple
    active processes of the same type for a single community.
    """
    name = models.CharField(max_length=30)
    callback_url = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(
        max_length=15,
        choices=[(s.value, s.name) for s in ProcessStatus],
        default=ProcessStatus.CREATED.value
    )
    plugin = models.ForeignKey(Plugin, models.CASCADE, related_name='plugin',
                               help_text="Plugin instance that this process belongs to")
    state = models.OneToOneField(DataStore,
                                 models.CASCADE,
                                 help_text="Datastore to persist any data",
                                 null=True)
    data = models.JSONField(default=dict, blank=True,
                            help_text="Data to serialize and send back to driver",)
    errors = models.JSONField(default=dict, blank=True)
    outcome = models.JSONField(default=dict, blank=True)
    input_schema = {}

    def __str__(self):
        return f"{self.plugin.name}.{self.name} for '{self.plugin.community.name}' ({self.pk}, {self.status})"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.state = DataStore.objects.create()
        super(AsyncProcess, self).save(*args, **kwargs)

    def start(self, parameters):
        pass

    def close(self):
        pass

    def receive_webhook(self, request):
        pass


@receiver(pre_save, sender=AsyncProcess, dispatch_uid="process_saved")
def notify_process_completed(sender, instance, **kwargs):
    """
    Pre-save receiver to notify caller that the governance processes has completed
    """

    def notify_completed(process):
        from metagov.core.serializers import AsyncProcessSerializer
        if not process.callback_url:
            logger.info("No callback url")
            return
        serializer = AsyncProcessSerializer(process)
        logger.info(
            f"Posting completed process outcome to {process.callback_url}")
        logger.info(serializer.data)
        resp = requests.post(process.callback_url, json=serializer.data)
        if not resp.ok:
            logger.error(
                f"Error posting outcome to callback url: {resp.status_code} {resp.text}")

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
