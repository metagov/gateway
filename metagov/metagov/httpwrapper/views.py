"""
This module contains views necessary for external drivers to interact with metagov. Django-based apps
can call the underlying methods directly.
"""
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
from metagov.httpwrapper.openapi_schemas import Tags
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


def index(request):
    return redirect("/redoc")


# Community endpoints


@swagger_auto_schema(
    method="post",
    operation_id="Create community",
    operation_description="Create a new community",
    request_body=MetagovSchemas.create_community_schema,
    responses={200: CommunitySerializer, 201: CommunitySerializer},
    tags=[Tags.COMMUNITY],
)
@api_view(["POST"])
def create_community(request):
    data = JSONParser().parse(request)
    community_serializer = CommunitySerializer(data=data)
    if not community_serializer.is_valid():
        return JsonResponse(community_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    community_serializer.save()
    return JsonResponse(community_serializer.data, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method="delete",
    operation_id="Delete community",
    manual_parameters=[MetagovSchemas.community_slug_in_path],
    operation_description="Delete an existing community",
    tags=[Tags.COMMUNITY],
)
@swagger_auto_schema(
    method="get",
    operation_id="Get community",
    operation_description="Get the configuration for an existing community",
    manual_parameters=[MetagovSchemas.community_slug_in_path],
    responses={200: CommunitySerializer},
    tags=[Tags.COMMUNITY],
)
@swagger_auto_schema(
    method="put",
    operation_id="Update community",
    operation_description="Update the configuration for an existing community",
    manual_parameters=[MetagovSchemas.community_slug_in_path],
    request_body=CommunitySerializer,
    responses={200: CommunitySerializer, 201: CommunitySerializer},
    tags=[Tags.COMMUNITY],
)
@api_view(["GET", "PUT", "DELETE"])
def community(request, slug):
    try:
        community = Community.objects.get(slug=slug)
    except Community.DoesNotExist:
        return HttpResponseNotFound()

    if request.method == "GET":
        # get community
        community_serializer = CommunitySerializer(community)
        return JsonResponse(community_serializer.data, safe=False)

    elif request.method == "PUT":
        # update community (change readable name or enable/disable plugins)
        data = JSONParser().parse(request)
        community_serializer = CommunitySerializer(community, data=data)
        if not community_serializer.is_valid():
            return JsonResponse(community_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        community_serializer.save()
        return JsonResponse(community_serializer.data)

    elif request.method == "DELETE":
        community.delete()
        return JsonResponse({"message": "Community was deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


# Plugin endpoints


def decorated_enable_plugin_view(plugin_name):
    """
    Decorate the `enable_plugin` view with swagger schema properties defined by the plugin author
    """
    cls = plugin_registry[plugin_name]

    @community_middleware
    @api_view(["POST"])
    def enable_plugin(request):
        plugin_config = JSONParser().parse(request)
        # Create or re-create the plugin (only one instance per community supported for now!)
        plugin, created = utils.create_or_update_plugin(plugin_name, plugin_config, request.community)
        # Serialize and return the Plugin instance
        serializer = PluginSerializer(plugin)
        resp_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return JsonResponse(serializer.data, status=resp_status)

    request_body_schema = utils.json_schema_to_openapi_object(cls.config_schema) if cls.config_schema else {}

    return swagger_auto_schema(
        method="post",
        responses={
            201: openapi.Response(
                "Plugin enabled",
                PluginSerializer,
            ),
            200: openapi.Response(
                "The Plugin was already enabled. Plugin was updated if the config changed.",
                PluginSerializer,
            ),
        },
        operation_id=f"Enable {plugin_name}",
        tags=[Tags.COMMUNITY],
        operation_description=f"Enable {plugin_name} plugin.",
        manual_parameters=[MetagovSchemas.community_header],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                **request_body_schema.get("properties", {}),
            },
            required=request_body_schema.get("required", []),
        ),
    )(enable_plugin)


@swagger_auto_schema(
    method="delete",
    operation_id="Disable plugin",
    operation_description="Delete a plugin instance. This is an irreversible action.",
    manual_parameters=[MetagovSchemas.plugin_name_in_path],
    responses={204: "Plugin disabled successfully"},
    tags=[Tags.COMMUNITY],
)
@api_view(["DELETE"])
def delete_plugin(request, plugin_name, id):
    try:
        plugin = Plugin.objects.get(pk=id)
    except Plugin.DoesNotExist:
        return HttpResponseNotFound()
    logger.info(f"Deleting plugin {plugin}")
    plugin.delete()
    return HttpResponse(status=status.HTTP_204_NO_CONTENT)


@swagger_auto_schema(**MetagovSchemas.plugin_authorize)
@api_view(["GET"])
def plugin_authorize(request, plugin_name):
    return metagov_handler.handle_oauth_authorize(request, plugin_name)


@swagger_auto_schema(method="GET", auto_schema=None)
@api_view(["GET"])
def plugin_auth_callback(request, plugin_name):
    """This function provides endpoints for plugins to provide to external platforms so that platforms
    can redirect ("call back") after oauth is complete."""
    return metagov_handler.handle_oauth_callback(request, plugin_name)


# Process endpoints


def decorated_create_process_view(plugin_name, slug):
    # get process model proxy class
    cls = plugin_registry[plugin_name]._process_registry[slug]
    prefixed_slug = f"{plugin_name}.{slug}"
    """
    Decorate the `create_process_endpoint` view with swagger schema properties defined by the plugin author
    """

    @community_middleware
    @api_view(["POST"])
    def create_process(request):
        # Look up plugin instance (throws if plugin is not installed for this community)
        # TODO(#50): change this to support multiple plugin instances of the same type
        plugin = get_plugin_instance(plugin_name, request.community)
        payload = JSONParser().parse(request)
        callback_url = payload.pop("callback_url", None)  # pop to remove it

        # Start a new process
        process = plugin.start_process(slug, callback_url, **payload)

        # Return 202 with resource location in header
        response = HttpResponse(status=HTTPStatus.ACCEPTED)
        response["Location"] = f"/{utils.construct_process_url(plugin_name, slug)}/{process.pk}"
        return response

    request_body_schema = utils.json_schema_to_openapi_object(cls.input_schema) if cls.input_schema else {}

    return swagger_auto_schema(
        method="post",
        responses={
            202: "Process successfully started. Use the URL from the `Location` header in the response to get the status and outcome of the process."
        },
        operation_id=f"Start {prefixed_slug}",
        tags=[Tags.GOVERNANCE_PROCESS],
        operation_description=f"Start a new governance process of type '{prefixed_slug}'",
        manual_parameters=[MetagovSchemas.community_header],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "callback_url": openapi.Schema(
                    type=openapi.TYPE_STRING, description="URL to POST outcome to when process is completed"
                ),
                **request_body_schema.get("properties", {}),
            },
            required=request_body_schema.get("required", []),
        ),
    )(create_process)


def decorated_get_process_view(plugin_name, slug):
    # get process model proxy class
    cls = plugin_registry[plugin_name]._process_registry[slug]
    prefixed_slug = f"{plugin_name}.{slug}"

    @swagger_auto_schema(
        method="delete",
        operation_id=f"Close {prefixed_slug}",
        operation_description=f"Close the {prefixed_slug} process",
        tags=[Tags.GOVERNANCE_PROCESS],
    )
    @swagger_auto_schema(
        method="get",
        operation_id=f"Check status of {prefixed_slug}",
        operation_description=f"Poll the pending {prefixed_slug} governance process",
        tags=[Tags.GOVERNANCE_PROCESS],
        responses={
            200: openapi.Response(
                "Current process record. Check the `status` field to see if the process has completed. If the `errors` field has data, the process failed.",
                GovernanceProcessSerializer,
            ),
            404: "Process not found",
        },
    )
    @api_view(["GET", "DELETE"])
    def get_process(request, process_id):
        try:
            process = cls.objects.get(pk=process_id)
        except cls.DoesNotExist:
            return HttpResponseNotFound()

        # 'DELETE'  means close the process and return it. This will update process state.
        if request.method == "DELETE":
            if process.status == ProcessStatus.COMPLETED.value:
                raise ValidationError("Can't close process, it has already completed")
            try:
                logger.info(f"Closing: {process}")
                process.close()
            except NotImplementedError:
                raise APIException(
                    f"{process.plugin.name}.{process.name} does not support manually closing the process."
                )
            if process.status != ProcessStatus.COMPLETED.value:
                raise APIException("Failed to close process")

        serializer = GovernanceProcessSerializer(process)
        logger.info(f"Returning serialized process: {serializer.data}")
        return JsonResponse(serializer.data)

    return get_process


# Action endpoints


def decorated_perform_action_view(plugin_name, slug, tags=[]):
    cls = plugin_registry[plugin_name]
    meta = cls._action_registry[slug]
    prefixed_slug = f"{plugin_name}.{slug}"

    @community_middleware
    @api_view(["POST"])
    def perform_action(request):
        """
        Perform an action on a platform
        """

        parameters = None
        if request.method == "POST" and request.body:
            payload = JSONParser().parse(request)
            parameters = payload.get("parameters", {})
            # TODO: add back support for GET. Should be allowed if params are simple enough.
        if request.method == "GET":
            parameters = request.GET.dict()  # doesnt support repeated params 'a=2&a=3'
            utils.restruct(parameters)

        community = request.community

        try:
            result = community.perform_action(
                plugin_name=plugin_name,
                action_id=slug,
                parameters=parameters,
                jsonschema_validation=True,
                # TODO(#50) add support for specifying comm platform id
                community_platform_id=None,
            )
        except Plugin.DoesNotExist:
            raise ValidationError(f"Plugin '{plugin_name}' not enabled for community '{community}'")
        except Plugin.MultipleObjectsReturned:
            raise ValidationError(
                f"Plugin '{plugin_name}' has multiple instances for community '{community}'. Please specify community_platform_id."
            )
        except jsonschema.exceptions.ValidationError as err:
            raise ValidationError(err.message)

        if result is None:
            return HttpResponse()
        try:
            return JsonResponse(result, safe=False)
        except TypeError:
            logger.error(f"Failed to serialize '{result}'")
            raise

    arg_dict = {
        "method": "post",
        "operation_description": meta.description,
        "manual_parameters": [MetagovSchemas.community_header],
        "operation_id": prefixed_slug,
        "tags": tags or [Tags.ACTION],
    }
    if meta.input_schema:
        properties = {"parameters": utils.json_schema_to_openapi_object(meta.input_schema)}

        arg_dict["request_body"] = openapi.Schema(type=openapi.TYPE_OBJECT, properties={**properties})

    if meta.output_schema:
        arg_dict["responses"] = {200: utils.json_schema_to_openapi_object(meta.output_schema)}
    else:
        arg_dict["responses"] = {200: "action was performed successfully"}

    return swagger_auto_schema(**arg_dict)(perform_action)


# Webhook endpoints


@csrf_exempt
@swagger_auto_schema(method="post", auto_schema=None)
@api_view(["POST"])
def receive_webhook(request, community, plugin_name, webhook_slug=None):
    """
    API endpoint for receiving webhook requests from external services
    """

    try:
        return metagov_handler.handle_incoming_webhook(
            request=request,
            plugin_name=plugin_name,
            community_slug=community,
            # FIXME #50 ?
            community_platform_id=None,
        )
    except (Community.DoesNotExist, Plugin.DoesNotExist):
        return HttpResponseNotFound()


@csrf_exempt
@swagger_auto_schema(method="post", auto_schema=None)
@api_view(["POST"])
def receive_webhook_global(request, plugin_name):
    """
    API endpoint for receiving webhook requests from external services.
    For plugins that receive events for multiple communities to a single URL -- like Slack and Discord
    """
    try:
        return metagov_handler.handle_incoming_webhook(
            request=request,
            plugin_name=plugin_name,
            # FIXME #50 ?
            community_platform_id=None,
        )
    except (Community.DoesNotExist, Plugin.DoesNotExist):
        return HttpResponseNotFound()