from metagov.core.models import Community


class MetagovApp:
    def __init__(self):
        pass

    @property
    def communities(self):
        return Community.objects.all()

    def get_community(self, slug) -> Community:
        return Community.objects.get(slug=slug)

    def create_community(self, readable_name="", slug=None) -> Community:
        if slug:
            return Community.objects.create(slug=slug, readable_name=readable_name)
        return Community.objects.create(readable_name=readable_name)

    def get_plugin_metadata(self, plugin_name):
        from metagov.core.plugin_manager import plugin_registry
        from metagov.core import utils

        cls = plugin_registry[plugin_name]
        return {
            "name": cls.name,
            "auth_type": cls.auth_type,
            "uses_webhook": utils.plugin_uses_webhooks(cls),
            "schemas": {
                "config": cls.config_schema,
                "actions": utils.get_action_schemas(cls),
                "events": utils.get_event_schemas(cls),
                "processes": utils.get_process_schemas(cls),
            },
        }
