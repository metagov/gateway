from django.conf.urls import url
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from django.contrib.auth.decorators import login_required
from metagov.core import views
from metagov.core.plugin_models import GovernanceProcessProvider, action_function_registry, resource_retrieval_registry

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
    # Create a new governance process
    post_pattern = path(
        f"api/internal/process/{slug}", views.decorated_create_process_view(slug), name=f"create_process_{slug}")
    # Get or close an existing governance process
    get_pattern = path(
        f"api/internal/process/{slug}/<int:process_id>", views.get_process, name=f"get_process_{slug}")

    plugin_patterns.append(post_pattern)
    plugin_patterns.append(get_pattern)

for (slug, item) in action_function_registry.registry.items():
    pattern = path(
        f"api/internal/action/{slug}", views.decorated_perform_action_view(slug), name=f"perform_{slug}")
    plugin_patterns.append(pattern)

for (slug, item) in resource_retrieval_registry.registry.items():
    pattern = path(
        f"api/internal/resource/{slug}", views.decorated_resource_view(slug), name=f"resource_{slug}")
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
    path('api/postreceive/<slug:slug>',
         views.receive_webhook, name='receive_webhook')
] + plugin_patterns
