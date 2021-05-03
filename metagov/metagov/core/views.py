import json
import logging
from http import HTTPStatus

import jsonschema
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    HttpResponseServerError,
    JsonResponse,
    QueryDict,
)
from django.shortcuts import render
from django.template import loader
from django.utils.decorators import decorator_from_middleware
from django.views.decorators.csrf import csrf_exempt
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from metagov.core import utils
from metagov.core.middleware import CommunityMiddleware, openapi_community_header
from metagov.core.models import Community, GovernanceProcess, Plugin, ProcessStatus
from metagov.core.openapi_schemas import Tags, community_schema
from metagov.core.plugin_decorators import plugin_registry
from metagov.core.serializers import CommunitySerializer, GovernanceProcessSerializer
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.schemas import AutoSchema
from rest_framework.views import APIView

community_middleware = decorator_from_middleware(CommunityMiddleware)

logger = logging.getLogger(__name__)

WEBHOOK_SLUG_CONFIG_KEY = "webhook_slug"


def index(request):
    return render(request, "login.html", {})


@login_required
def home(request):
    return HttpResponse(f"<p>hello {request.user.username}!</p><a href='/admin'>Site Admin</a>")


@swagger_auto_schema(
    method="delete",
    operation_id="Delete community",
    operation_description="Delete the community",
    tags=[Tags.COMMUNITY],
)
@swagger_auto_schema(
    method="get", operation_id="Get community", responses={200: community_schema}, tags=[Tags.COMMUNITY]
)
@swagger_auto_schema(
    method="put",
    operation_id="Create or update community",
    request_body=community_schema,
    responses={200: community_schema, 200: community_schema},
    tags=[Tags.COMMUNITY],
)
@api_view(["GET", "PUT", "DELETE"])
def community(request, name):
    if request.method == "GET":
        try:
            community = Community.objects.get(name=name)
        except Community.DoesNotExist:
            return HttpResponseNotFound()

        community_serializer = CommunitySerializer(community)
        return JsonResponse(community_serializer.data, safe=False)

    elif request.method == "PUT":
        data = JSONParser().parse(request)
        created = False
        try:
            community = Community.objects.get(name=name)
            community_serializer = CommunitySerializer(community, data=data)
        except Community.DoesNotExist:
            if data.get("name") != name:
                # if creating a new community, the name and slug should match
                return HttpResponseBadRequest(f"Expected name {name}, found {data.get('name')}")
            community_serializer = CommunitySerializer(data=data)
            created = True

        if community_serializer.is_valid():
            community_serializer.save()
            s = status.HTTP_201_CREATED if created else status.HTTP_200_OK
            return JsonResponse(community_serializer.data, status=s)
        return JsonResponse(community_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        try:
            community = Community.objects.get(name=name)
        except Community.DoesNotExist:
            return HttpResponseNotFound()
        community.delete()
        return JsonResponse({"message": "Community was deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


@swagger_auto_schema(method="get", operation_id="List community web hook receivers", tags=[Tags.COMMUNITY])
@api_view(["GET"])
def list_hooks(request, name):
    try:
        community = Community.objects.get(name=name)
    except Community.DoesNotExist:
        return HttpResponseNotFound()

    plugins = Plugin.objects.filter(community=community)
    hooks = []
    for p in list(plugins):
        url = f"/api/hooks/{name}/{p.name}"
        if p.config and p.config.get(WEBHOOK_SLUG_CONFIG_KEY):
            url += "/" + p.config.get(WEBHOOK_SLUG_CONFIG_KEY)
        hooks.append(url)
    return JsonResponse({"hooks": hooks})


@csrf_exempt
@swagger_auto_schema(method="post", auto_schema=None)
@api_view(["POST"])
def receive_webhook(request, community, plugin_name, webhook_slug=None):
    """
    API endpoint for receiving webhook requests from external services
    """

    try:
        community = Community.objects.get(name=community)
    except Community.DoesNotExist:
        return HttpResponseNotFound()

    # Lookup plugin
    plugin = get_plugin_instance(plugin_name, community)

    # Validate slug if the plugin has `webhook_slug` configured
    expected_slug = plugin.config.get(WEBHOOK_SLUG_CONFIG_KEY)
    if webhook_slug != expected_slug:
        logger.error(f"Received request at {webhook_slug}, expected {expected_slug}. Rejecting.")
        return HttpResponseBadRequest()

    logger.info(f"Passing webhook request to: {plugin}")
    plugin.receive_webhook(request)

    # Call `receive_webhook` on each of the GovernanceProcess proxy models
    proxy_models = plugin_registry[plugin_name]._process_registry.values()
    for cls in proxy_models:
        processes = cls.objects.filter(plugin=plugin, status=ProcessStatus.PENDING.value)
        logger.info(f"{processes.count()} pending processes for plugin instance '{plugin}'")
        for process in processes:
            logger.info(f"Passing webhook request to: {process}")
            try:
                process.receive_webhook(request)
            except Exception as e:
                logger.error(e)

    return HttpResponse()


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
        plugin = get_plugin_instance(plugin_name, request.community)
        payload = JSONParser().parse(request)
        callback_url = payload.pop("callback_url", None)  # pop to remove it

        # Validate payload
        if cls.input_schema:
            try:
                jsonschema.validate(payload, cls.input_schema)
            except jsonschema.exceptions.ValidationError as err:
                raise ValidationError(err.message)

        # Create new process instance
        new_process = cls.objects.create(name=slug, callback_url=callback_url, plugin=plugin)
        logger.info(f"Created process: {new_process}")

        # Start process
        try:
            new_process.start(payload)
        except APIException as e:
            new_process.delete()
            raise e
        except Exception as e:
            # Catch any other exceptions so that we can delete the model.
            new_process.delete()
            raise e

        logger.info(f"Started process: {new_process}")

        # return 202 with resource location in header
        response = HttpResponse(status=HTTPStatus.ACCEPTED)
        response["Location"] = f"/{utils.construct_process_url(plugin_name, slug)}/{new_process.pk}"
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
        manual_parameters=[openapi_community_header],
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

        # This is a hack so that the process can access proxy-specific functions..
        process.plugin = get_proxy(process.plugin)

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

        # If the process is pending, poll it. This may update process state.
        if process.status == ProcessStatus.PENDING.value:
            logger.info(f"Checking status of: {process}")
            process.check_status()

        serializer = GovernanceProcessSerializer(process)
        logger.info(f"Returning serialized process: {serializer.data}")
        return JsonResponse(serializer.data)

    return get_process


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
        # 1. Look up plugin instance
        plugin = get_plugin_instance(plugin_name, request.community)

        action_function = getattr(plugin, meta.function_name)

        # 2. Validate input parameters
        parameters = {}
        if request.method == "POST" and request.body:
            payload = JSONParser().parse(request)
            parameters = payload.get("parameters")
            # TODO: add back support for GET. Should be allowed if params are simple enough.
        if request.method == "GET":
            parameters = request.GET.dict()  # doesnt support repeated params 'a=2&a=3'
            utils.restruct(parameters)

        if meta.input_schema:
            try:
                jsonschema.validate(parameters, meta.input_schema)
            except jsonschema.exceptions.ValidationError as err:
                raise ValidationError(err.message)

        # 3. Invoke action function
        response = action_function(parameters)

        # 4. Validate response
        if meta.output_schema:
            try:
                jsonschema.validate(response, meta.output_schema)
            except jsonschema.exceptions.ValidationError as err:
                raise ValidationError(err.message)

        # 5. Return response
        return JsonResponse(response)

    arg_dict = {
        "method": "post",
        "operation_description": meta.description,
        "manual_parameters": [openapi_community_header],
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


def get_plugin_instance(plugin_name, community):
    """get the right proxy of a plugin instance"""
    cls = plugin_registry.get(plugin_name)
    if not cls:
        raise ValidationError(f"Plugin '{plugin_name}' not found")

    plugin = cls.objects.filter(name=plugin_name, community=community).first()
    if not plugin:
        raise ValidationError(f"Plugin '{plugin_name}' not enabled for community '{community.name}'")
    return plugin


def get_proxy(plugin):
    cls = plugin_registry.get(plugin.name)
    return cls.objects.get(pk=plugin.pk)