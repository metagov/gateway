import logging
from http import HTTPStatus

import jsonschema
import metagov.httpwrapper.openapi_schemas as MetagovSchemas
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import decorator_from_middleware
from django.views.decorators.csrf import csrf_exempt
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from metagov.core import utils
from metagov.core.app import MetagovApp
from metagov.core.handlers import MetagovRequestHandler
from metagov.core.middleware import CommunityMiddleware
from metagov.core.models import Community, Plugin, ProcessStatus
from metagov.core.plugin_manager import plugin_registry
from metagov.core.serializers import CommunitySerializer, GovernanceProcessSerializer, PluginSerializer
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.parsers import JSONParser

community_middleware = decorator_from_middleware(CommunityMiddleware)

logger = logging.getLogger(__name__)


metagov_app = MetagovApp()
metagov_handler = MetagovRequestHandler(app=metagov_app)




# FIXME: it feels like this should be in HTTPWrapper but might a Django-based driver want a
# convenience method for accessing schemas?
@swagger_auto_schema(**MetagovSchemas.plugin_metadata)
@api_view(["GET"])
def plugin_metadata(request, plugin_name):
    cls = plugin_registry.get(plugin_name)
    if not cls:
        return HttpResponseBadRequest(f"No such plugin: {plugin_name}")

    data = metagov_app.get_plugin_metadata(plugin_name)
    return JsonResponse(data)

# FIXME: it feels like this should be in HTTPWrapper but might a Django-based driver want a
# convenience method for accessing schemas?
@swagger_auto_schema(**MetagovSchemas.plugin_schemas)
@api_view(["GET"])
def plugin_config_schemas(request):
    plugins = {}
    for (name, cls) in plugin_registry.items():
        plugins[name] = cls.config_schema
    return JsonResponse(plugins)



