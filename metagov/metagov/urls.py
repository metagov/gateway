import logging

from django.conf.urls import url
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from metagov.core import utils, views
from metagov.httpwrapper.urls import management_patterns, identity_patterns, plugin_patterns


logger = logging.getLogger(__name__)

schema_view = get_schema_view(
    openapi.Info(
        title="Metagov Prototype API",
        default_version="v1",
        description="""
Metagov is a unified API gateway for digital governance services. It’s designed to support rapid prototyping of governance systems, decision-making processes, and social workflows across a range of platforms, from forums to chat services to blockchains. To help people prototype, Metagov ships with a powerful driver for authoring governance policies over multiple platforms.

Metagov is a prototype under active development, so please help us out by sending us feedback at hello@metagov.org or by opening an issue on our GitHub.

See the full documentation at https://docs.metagov.org/

> Endpoints that are prefixed with `/internal` are exposed **only to the local network** and accessed by the collocated "governance driver."
""",
        # contact=openapi.Contact(email="hello@metagov.org"),
        # license=openapi.License(name="MIT License"),
        x_logo={"url": "https://metagov.org/wp-content/uploads/2019/09/logo-copy-150x150.png", "href": "#"},
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)


urlpatterns = [

    path("", views.index, name="index"),
    # path("schema/", Schema.as_view()),
    path("admin/", admin.site.urls),

    url(r"^swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    url(r"^swagger/$", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    url(r"^redoc/$", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),

    path("api/hooks/<slug:community>/<slug:plugin_name>", views.receive_webhook, name="receive_webhook"),
    path(
        "api/hooks/<slug:community>/<slug:plugin_name>/<slug:webhook_slug>",
        views.receive_webhook,
        name="receive_webhook",
    ),
    path("api/hooks/<slug:plugin_name>", views.receive_webhook_global, name="receive_webhook_global"),

    # callback URL for oauth flow. this is where code is exchanged for a token, and the plugin is enabled for the community.
    path("auth/<slug:plugin_name>/callback", views.plugin_auth_callback, name="plugin_auth_callback"),
    path(
        f"{utils.internal_path}/plugin-schemas",
        views.plugin_config_schemas,
        name="plugin_config_schemas",
    ),

    # Get public metadata about a plugin type
    path(f"{utils.internal_path}/plugin/<slug:plugin_name>/metadata", views.plugin_metadata, name="plugin_metadata"),

] + plugin_patterns + management_patterns + identity_patterns
