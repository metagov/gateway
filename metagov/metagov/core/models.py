import json
import logging

import jsonschema
import requests
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from metagov.core.plugin_decorators import plugin_registry
from metagov.core.plugin_models import (GovernanceProcessProvider,
                                        ProcessState, ProcessStatus)
from metagov.core.validators import DefaultValidatingDraft7Validator
from rest_framework import serializers

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


class PluginSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plugin
        fields = ('name', 'config')


def create_or_update_plugin(plugin_name, plugin_config, community):
    cls = plugin_registry.get(plugin_name)
    if not cls:
        raise Exception(f"No such plugin registered: {plugin_name}")

    if cls.config_schema:
        try:
            # this mutates `plugin_config` by filling in default values from schema
            DefaultValidatingDraft7Validator(
                cls.config_schema).validate(plugin_config)
            print(plugin_config)
        except jsonschema.exceptions.ValidationError as err:
            raise serializers.ValidationError(
                f"Schema validation error: {err.message}")

    try:
        plugin = cls.objects.get(
            name=plugin_name,
            community=community
        )
    except cls.DoesNotExist:
        inst = cls.objects.create(
            name=plugin_name,
            community=community,
            config=plugin_config
        )
        logger.info(f"Created plugin '{inst}'")
    else:
        if plugin.config != plugin_config:
            # TODO what happens to pending processes?
            logger.info(
                f"Destroying and re-creating '{plugin}' to apply config change")
            plugin.delete()
            cls.objects.create(
                name=plugin_name,
                community=community,
                config=plugin_config
            )
        else:
            logger.info(f"Not updating '{plugin}', no change in config.")


class CommunitySerializer(serializers.ModelSerializer):
    plugins = PluginSerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = Community
        fields = ('name', 'readable_name', 'plugins')

    def update(self, instance, validated_data):
        for data in validated_data.get('plugins'):
            logger.info(
                f"Updating community '{instance}' plugin {data.get('name')}...")
            create_or_update_plugin(
                plugin_name=data.get('name'),
                plugin_config=data.get('config'),
                community=instance
            )

        # deactivate any plugins that are not present in `plugins` (that means they are being deactivated)
        active_plugins = [p.get('name')
                          for p in validated_data.get('plugins')]
        plugins = Plugin.objects.filter(community=instance)
        for inst in plugins:
            if inst.name not in active_plugins:
                logger.info(f"Deactivating plugin '{inst}'")
                # TODO what happens to pending processes?
                inst.delete()

        instance.name = validated_data.get('name', instance.name)
        instance.readable_name = validated_data.get(
            'readable_name', instance.readable_name)
        instance.save()
        return instance

    def create(self, validated_data):
        plugins = validated_data.pop('plugins')
        instance = Community.objects.create(**validated_data)
        for data in plugins:
            create_or_update_plugin(
                plugin_name=data.get('name'),
                plugin_config=data.get('config'),
                community=instance
            )
        return instance


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
