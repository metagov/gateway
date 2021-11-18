from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "metagov.core"
    verbose_name = "Metagov App"

    def ready(self):
        from metagov.core import signals
        from metagov.core.signals import handlers
        from metagov.core.plugin_manager import plugin_registry

        print(f"Metagov App Ready. Installed plugins: {list(plugin_registry.keys())}")
