from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "metagov.core"

    def ready(self):
        from metagov.core import signals
