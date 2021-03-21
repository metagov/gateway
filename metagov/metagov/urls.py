import logging

from django.conf.urls import url
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from metagov.core import views
from metagov.core.plugin_decorators import plugin_registry
from metagov.core.plugin_models import (GovernanceProcessProvider,
                                        action_function_registry,
                                        resource_retrieval_registry)

logger = logging.getLogger('django')

# TODO add community header to generated openapi docs

schema_view = get_schema_view(
    openapi.Info(
        title="Metagov API",
        default_version='v1',
        description="""
        Service for accessing governance resources and invoking governance processes. This documentation shows endpoints defined by plugins that are installed on this instance of Metagov.
        
        **Endpoints that start with `/api/internal` can only be accessed on the local network.**
        """,
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

plugin_patterns = []

# FIXME convert to new plugin system
for slug in GovernanceProcessProvider.plugins.keys():
    # Create a new governance process
    post_pattern = path(
        f"api/internal/process/{slug}", views.decorated_create_process_view(slug), name=f"create_process_{slug}")
    # Get or close an existing governance process
    get_pattern = path(
        f"api/internal/process/{slug}/<int:process_id>", views.get_process, name=f"get_process_{slug}")

    plugin_patterns.append(post_pattern)
    plugin_patterns.append(get_pattern)


for (key, cls) in plugin_registry.items():
    for (slug, meta) in cls._resource_registry.items():
        prefixed_slug = f"{cls.name}.{slug}"
        route = f"api/internal/resource/{prefixed_slug}"
        logger.info(f"Adding route: {route}")
        pattern = path(route, views.decorated_resource_view(
            cls.name, slug), name=f"resource_{prefixed_slug}")
        plugin_patterns.append(pattern)

    for (slug, meta) in cls._action_registry.items():
        prefixed_slug = f"{cls.name}.{slug}"
        route = f"api/internal/action/{prefixed_slug}"
        logger.info(f"Adding route: {route}")
        pattern = path(route, views.decorated_perform_action_view(
            cls.name, slug), name=f"perform_{prefixed_slug}")
        plugin_patterns.append(pattern)

# TODO: Add endpoints to expose schemas for actions, processes, and resources
admin.site.login = login_required(admin.site.login)

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'home', views.home, name='home'),
    url('', include('social_django.urls', namespace='social')),
    path('', views.index, name='index'),
    path('admin/', admin.site.urls),
    url(r'^swagger(?P<format>\.json|\.yaml)$',
        schema_view.without_ui(cache_timeout=0), name='schema-json'),
    url(r'^swagger/$', schema_view.with_ui('swagger',
                                           cache_timeout=0), name='schema-swagger-ui'),
    url(r'^redoc/$', schema_view.with_ui('redoc',
                                         cache_timeout=0), name='schema-redoc'),
    path('api/postreceive/<int:community_id>/<slug:plugin_name>/<slug:webhook_slug>',
         views.receive_webhook, name='receive_webhook'),
    path('api/internal/community/<slug:name>',
         views.community, name='community')
] + plugin_patterns
