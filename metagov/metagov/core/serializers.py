import logging

import jsonschema
from metagov.core import utils
from metagov.core.models import Community, GovernanceProcess, Plugin, ProcessStatus
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)


class PluginSerializer(serializers.ModelSerializer):
    community = serializers.SerializerMethodField()
    auth_type = serializers.SerializerMethodField()

    class Meta:
        model = Plugin
        # TODO: include date enabled and user who enabled it
        fields = ("id", "name", "config", "community", "auth_type")

    def get_community(self, inst):
        return inst.community.slug

    def get_auth_type(self, inst):
        from metagov.core.plugin_manager import plugin_registry

        cls = plugin_registry[inst.name]
        return cls.auth_type


class CommunitySerializer(serializers.ModelSerializer):
    plugins = PluginSerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = Community
        fields = ("slug", "readable_name", "plugins")

    def update(self, instance, validated_data):
        plugins = validated_data.get("plugins") or []
        for data in plugins:
            try:
                instance.enable_plugin(data.get("name"), data.get("config"))
            except jsonschema.exceptions.ValidationError as err:
                raise ValidationError(f"ValidationError: {err.message}")
            except ValueError as err:
                if "No such plugin" in str(err):
                    raise ValidationError(err)
                raise

        # deactivate any plugins that are not present in `plugins` (that means they are being deactivated)
        active_plugins = [p.get("name") for p in plugins]
        plugins = Plugin.objects.filter(community=instance)
        for inst in plugins:
            if inst.name not in active_plugins:
                logger.info(f"Deactivating plugin '{inst}'")
                # TODO what happens to pending processes?
                inst.delete()

        instance.slug = validated_data.get("slug", instance.slug)
        instance.readable_name = validated_data.get("readable_name", instance.readable_name)
        instance.save()

        return instance

    def create(self, validated_data):
        logger.debug(f"Creating community from data: {validated_data}")
        plugins = validated_data.get("plugins") or []
        validated_data.pop("plugins", None)
        instance = Community.objects.create(**validated_data)
        for data in plugins:
            utils.create_or_update_plugin(
                plugin_name=data.get("name"), plugin_config=data.get("config"), community=instance
            )
        return instance


class GovernanceProcessSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    community = serializers.SerializerMethodField()
    # TODO nothing is actually validating this field
    status = serializers.ChoiceField(choices=[(s.value, s.name) for s in ProcessStatus])

    class Meta:
        model = GovernanceProcess
        fields = ("id", "name", "community", "status", "url", "errors", "outcome")

    def get_name(self, inst):
        return f"{inst.plugin.name}.{inst.name}"

    def get_community(self, inst):
        return inst.plugin.community.slug
