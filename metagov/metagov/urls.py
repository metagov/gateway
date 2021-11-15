from django.contrib import admin
from django.urls import include, path

from metagov.core import utils, views
from metagov.httpwrapper.urls import httpwrapper_patterns


urlpatterns = [

    path("admin/", admin.site.urls),

    path(
        f"{utils.internal_path}/plugin-schemas",
        views.plugin_config_schemas,
        name="plugin_config_schemas",
    ),

    # Get public metadata about a plugin type
    path(f"{utils.internal_path}/plugin/<slug:plugin_name>/metadata", views.plugin_metadata, name="plugin_metadata"),

] + httpwrapper_patterns