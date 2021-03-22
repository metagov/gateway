import logging

import jsonschema
from metagov.core.models import Community, Plugin, AsyncProcess, ProcessStatus
from metagov.core.plugin_decorators import plugin_registry
from metagov.core.validators import DefaultValidatingDraft7Validator
from rest_framework import serializers

logger = logging.getLogger('django')


def create_or_update_plugin(plugin_name, plugin_config, community):
    cls = plugin_registry.get(plugin_name)
    if not cls:
        raise Exception(f"No such plugin registered: {plugin_name}")

    if cls.config_schema:
        try:
            # this mutates `plugin_config` by filling in default values from schema
            DefaultValidatingDraft7Validator(
                cls.config_schema).validate(plugin_config)
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


class PluginSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plugin
        fields = ('name', 'config')


class CommunitySerializer(serializers.ModelSerializer):
    plugins = PluginSerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = Community
        fields = ('name', 'readable_name', 'plugins')

    def update(self, instance, validated_data):
        for data in validated_data.get('plugins'):
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


class AsyncProcessSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    community = serializers.SerializerMethodField()
    # TODO nothing is actually validating this field
    status = serializers.ChoiceField(
        choices=[(s.value, s.name) for s in ProcessStatus])

    class Meta:
        model = AsyncProcess
        fields = ('id', 'name', 'community', 'status',
                  'data', 'errors', 'outcome')

    def get_name(self, inst):
        return f"{inst.plugin.name}.{inst.name}"

    def get_community(self, inst):
        return inst.plugin.community.name
