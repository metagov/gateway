from django.conf.urls import url
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from metagov.core import views
from metagov.core.plugin_models import GovernanceProcessProvider

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

for slug in GovernanceProcessProvider.plugins.keys():
    create_process = views.create_process_endpoint(slug)
    post_pattern = path(
        f"api/internal/process/{slug}", views.decorated_create_process_view(slug), name=f"create_{slug}")
    get_pattern = path(
        f"api/internal/process/{slug}/<int:process_id>", views.get_process, name=f"get_{slug}")
    plugin_patterns.append(post_pattern)
    plugin_patterns.append(get_pattern)

urlpatterns = [
    path('', views.index, name='index'),
    url(r'^swagger(?P<format>\.json|\.yaml)$',
        schema_view.without_ui(cache_timeout=0), name='schema-json'),
    url(r'^swagger/$', schema_view.with_ui('swagger',
                                           cache_timeout=0), name='schema-swagger-ui'),
    url(r'^redoc/$', schema_view.with_ui('redoc',
                                         cache_timeout=0), name='schema-redoc'),
    path('api/internal/resource/<slug:resource_name>',
         views.get_resource, name='get_resource'),
    path('api/postreceive/<slug:slug>',
         views.receive_webhook, name='receive_webhook')
] + plugin_patterns
