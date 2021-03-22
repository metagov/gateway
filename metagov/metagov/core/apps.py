from django.apps import AppConfig
# from constance.apps import ConstanceConfig

class CoreConfig(AppConfig):
    name = 'metagov.core'

# subclass ConstanceConfig to rename it in the django admin site
# class CustomConstance(ConstanceConfig):
#     verbose_name = "Plugin Configuration"
