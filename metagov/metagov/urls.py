import logging

from django.conf.urls import url
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
# from schema_graph.views import Schema

from metagov.core import views
from metagov.core import utils
from metagov.core.plugin_decorators import plugin_registry

logger = logging.getLogger('django')

# TODO: Add endpoints to expose schemas for actions, processes, and resources

schema_view = get_schema_view(
    openapi.Info(
        title="Metagov API",
        default_version='v1',
        description="""
        Service for accessing governance resources and invoking governance processes.

        Endpoints are meant to be exposed **only to the local network** and accessed by the collocated "governance driver."
        """,
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

plugin_patterns = []

for (key, cls) in plugin_registry.items():
    for (slug, meta) in cls._action_registry.items():
        # Perform an action
        route = utils.construct_action_url(cls.name, slug)
        view = views.decorated_perform_action_view(cls.name, slug)
        plugin_patterns.append(path(route, view))

    for (slug, meta) in cls._resource_registry.items():
        # Get a resource
        route = utils.construct_resource_url(cls.name, slug)
        view = views.decorated_resource_view(cls.name, slug)
        plugin_patterns.append(path(route, view))

    for (slug, process_cls) in cls._process_registry.items():
        # Create a new governance process
        route = utils.construct_process_url(cls.name, slug)
        view = views.decorated_create_process_view(cls.name, slug)
        plugin_patterns.append(path(route, view))

        # Get or close an existing governance process
        plugin_patterns.append(path(f"{route}/<int:process_id>", views.get_process))

# admin.site.login = login_required(admin.site.login)

# debug logging
new_routes = [str(p.pattern) for p in plugin_patterns]
new_routes.sort()
logger.info(f"Adding routes:")
logger.info('\n'.join(new_routes))


urlpatterns = [
    # url(r'^$', views.index, name='index'),
    # url(r'home', views.home, name='home'),
    # url('', include('social_django.urls', namespace='social')),
    path('', views.index, name='index'),
    # path("schema/", Schema.as_view()),
    path('admin/', admin.site.urls),
    url(r'^swagger(?P<format>\.json|\.yaml)$',
        schema_view.without_ui(cache_timeout=0), name='schema-json'),
    url(r'^swagger/$', schema_view.with_ui('swagger',
                                           cache_timeout=0), name='schema-swagger-ui'),
    url(r'^redoc/$', schema_view.with_ui('redoc',
                                         cache_timeout=0), name='schema-redoc'),
    path('api/hooks/<slug:community>/<slug:plugin_name>',
         views.receive_webhook, name='receive_webhook'),
    path('api/hooks/<slug:community>/<slug:plugin_name>/<slug:webhook_slug>',
         views.receive_webhook, name='receive_webhook'),
    path(f"{utils.internal_path}/community/<slug:name>",
         views.community, name='community')
] + plugin_patterns
