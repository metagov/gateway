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
from rest_framework import serializers

logger = logging.getLogger('django')


def validate_process_name(name):
    PluginClass = GovernanceProcessProvider.plugins.get(name)
    if not PluginClass:
        raise ValidationError(
            _('%(name)s is not a registered governance process'),
            params={'name': name},
        )


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

    def cancel(self):
        """cancel governance process"""
        pass

    def close(self):
        """close governance process, return outcome"""
        return None

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


class GovernanceProcessSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=50, allow_blank=False)
    name = serializers.SlugField(
        max_length=50, min_length=None, allow_blank=False)
    status = serializers.ChoiceField(
        choices=[(s.value, s.name) for s in ProcessStatus])
    data = serializers.JSONField()
    errors = serializers.JSONField()
    outcome = serializers.JSONField()

    def create(self, validated_data):
        return GovernanceProcess.objects.create(**validated_data)


# notify driver that process has completed
def notify_completed(process):
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
