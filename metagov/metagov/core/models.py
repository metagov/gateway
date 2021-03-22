import json
import logging


import requests
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi

from metagov.core.plugin_models import (GovernanceProcessProvider,
                                        ProcessState, ProcessStatus)

logger = logging.getLogger('django')


class Community(models.Model):
    name = models.CharField(max_length=30, primary_key=True)
    readable_name = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.readable_name} ({self.name})"


class DataStore(models.Model):
    # FIXME copied from policykit -- use JSON field instead
    data_store = models.TextField()

    def _get_data_store(self):
        if self.data_store != '':
            return json.loads(self.data_store)
        else:
            return {}

    def _set_data_store(self, obj):
        self.data_store = json.dumps(obj)
        self.save()

    def get(self, key):
        obj = self._get_data_store()
        return obj.get(key, None)

    def set(self, key, value):
        obj = self._get_data_store()
        obj[key] = value
        self._set_data_store(obj)
        return True

    def remove(self, key):
        obj = self._get_data_store()
        res = obj.pop(key, None)
        self._set_data_store(obj)
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
    config_schema = {}  # can be overridden to set jsonschema of config
    data = models.OneToOneField(DataStore,
                                models.CASCADE,
                                help_text="Datastore to persist any data"
                                )

    class Meta:
        unique_together = ['name', 'community']

    def __str__(self):
        return f"{self.name} for {self.community.name}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.data = DataStore.objects.create()
            self.initialize()
        super(Plugin, self).save(*args, **kwargs)

    def initialize(self):
        pass

    def receive_webhook(self, request):
        pass



def validate_process_name(name):
    PluginClass = GovernanceProcessProvider.plugins.get(name)
    if not PluginClass:
        raise ValidationError(
            _('%(name)s is not a registered governance process'),
            params={'name': name},
        )

# FIXME 👽 👽 👽 👽 👽


class GovernanceProcess(models.Model):
    name = models.CharField(max_length=30, validators=[
                            validate_process_name], null=True)
    callback_url = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(
        max_length=15,
        choices=[(s.value, s.name) for s in ProcessStatus],
        default=ProcessStatus.CREATED.value
    )
    data = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=dict, blank=True)
    outcome = models.JSONField(default=dict, blank=True)

    # FIXME make nicer https://docs.djangoproject.com/en/3.1/ref/models/instances/
    # only needs the one selected plugin
    plugins = GovernanceProcessProvider.plugins

    def save(self, *args, **kwargs):
        super(GovernanceProcess, self).save(*args, **kwargs)

    def start(self, parameters):
        PluginClass = self.plugins.get(self.name)
        process_state = ProcessState(self)
        PluginClass.start(process_state, parameters)

    def close(self):
        """close governance process, update outcome in state"""
        PluginClass = self.plugins.get(self.name)
        process_state = ProcessState(self)
        PluginClass.close(process_state)

    def __str__(self):
        return self.name

    def handle_webhook(self, request):
        """process webhook, possibly updating state"""
        PluginClass = self.plugins.get(self.name)
        process_state = ProcessState(self)
        PluginClass.handle_webhook(process_state, request)


@receiver(pre_save, sender=GovernanceProcess, dispatch_uid="process_saved")
def notify_process_completed(sender, instance, **kwargs):
    """
    Pre-save receiver to notify caller that the governance processes has completed
    """
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


# notify driver that process has completed
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
        logger.error(
            f"Error posting outcome to callback url: {resp.status_code} {resp.text}")
