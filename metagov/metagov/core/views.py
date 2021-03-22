import json
import logging
from http import HTTPStatus

import jsonschema
from constance.signals import config_updated
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseNotFound, HttpResponseServerError,
                         JsonResponse, QueryDict)
from django.shortcuts import render
from django.template import loader
from django.utils.decorators import decorator_from_middleware
from django.views.decorators.csrf import csrf_exempt
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from jsonschema_to_openapi.convert import convert
from metagov.core.middleware import (CommunityMiddleware,
                                     openapi_community_header)
from metagov.core.models import AsyncProcess, Community
from metagov.core.plugin_decorators import plugin_registry
from metagov.core.serializers import (AsyncProcessSerializer,
                                      CommunitySerializer)
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.parsers import JSONParser
from rest_framework.schemas import AutoSchema
from rest_framework.views import APIView

community_middleware = decorator_from_middleware(CommunityMiddleware)

logger = logging.getLogger('django')


def index(request):
    return render(request, 'login.html', {})


@login_required
def home(request):
    return HttpResponse(f"<p>hello {request.user.username}!</p><a href='/admin'>Site Admin</a>")


@swagger_auto_schema(method='delete',
                     operation_description="Close an existing governance process")
@swagger_auto_schema(method='get',
                     operation_description="Get the status of an existing governance process",
                     responses={
                            200: openapi.Response(
                                'Current process record. Check the `status` field to see if the process has completed. If the `errors` field has data, the process failed.', AsyncProcessSerializer),
                            404: 'Process not found'})
@api_view(['GET', 'DELETE'])
def get_process(request, process_id):
    try:
        process = AsyncProcess.objects.get(pk=process_id)
    except AsyncProcess.DoesNotExist:
        return HttpResponseNotFound()

    if request.method == 'DELETE':
        # 'DELETE'  means close the process and return it
        # If 'close' is implemented, it should set the status to COMPLETED
        logger.info(f"Closing process {process_id}")
        process.close()

    serializer = AsyncProcessSerializer(process)
    logger.info(f"Returning serialized process: {serializer.data}")
    return JsonResponse(serializer.data)


@api_view(['GET', 'PUT', 'DELETE'])
def community(request, name):
    if request.method == 'GET':
        try:
            community = Community.objects.get(name=name)
        except Community.DoesNotExist:
            return HttpResponseNotFound()

        community_serializer = CommunitySerializer(community)
        return JsonResponse(community_serializer.data, safe=False)

    elif request.method == 'PUT':
        data = JSONParser().parse(request)
        try:
            community = Community.objects.get(name=name)
            community_serializer = CommunitySerializer(community, data=data)
        except Community.DoesNotExist:
            if data.get('name') != name:
                # if creating a new community, the name and slug should match
                return HttpResponseBadRequest(f"Expected name {name}, found {data.get('name')}")
            community_serializer = CommunitySerializer(data=data)

        if community_serializer.is_valid():
            community_serializer.save()
            return JsonResponse(community_serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(community_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        try:
            community = Community.objects.get(name=name)
        except Community.DoesNotExist:
            return HttpResponseNotFound()
        community.delete()
        return JsonResponse({'message': 'Community was deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


@csrf_exempt
def receive_webhook(request, community, plugin_name, webhook_slug=None):
    """
    API endpoint for receiving webhook requests from external services
    """

    try:
        community = Community.objects.get(name=community)
    except Community.DoesNotExist:
        return HttpResponseNotFound()

    # Lookup plugin
    try:
        plugin = get_plugin_instance(plugin_name, community)
    except Exception as e:
        return HttpResponseBadRequest(e)

    # Validate slug if the plugin has `webhook_slug` configured
    expected_slug = plugin.config.get('webhook_slug')
    if webhook_slug != expected_slug:
        logger.error(
            f"Received request at {webhook_slug}, expected {expected_slug}. Rejecting.")
        return HttpResponseBadRequest()

    logger.info(f"Passing webhook request to: {plugin}")
    plugin.receive_webhook(request)

    # Call `receive_webhook` on each of the AsyncProcess proxy models
    proxy_models = plugin_registry[plugin_name]._process_registry.values()
    for cls in proxy_models:
        processes = cls.objects.filter(plugin=plugin)
        for process in processes:
            logger.info(f"Passing webhook request to: {process}")
            process.receive_webhook(request)

    return HttpResponse()


def decorated_create_process_view(plugin_name, slug):
    # get process model proxy class
    cls = plugin_registry[plugin_name]._process_registry[slug]
    """
    Decorate the `create_process_endpoint` view with swagger schema properties defined by the plugin author
    """
    @community_middleware
    @api_view(['POST'])
    def create_process(request):
        # Look up plugin instance (throws if plugin is not installed for this community)
        try:
            plugin = get_plugin_instance(plugin_name, request.community)
        except Exception as e:
            return HttpResponseBadRequest(e)

        payload = JSONParser().parse(request)
        callback_url = payload.pop('callback_url', None)  # pop to remove it

        # Validate payload
        try:
            if cls.input_schema:
                jsonschema.validate(payload, cls.input_schema)
        except jsonschema.exceptions.ValidationError as err:
            return HttpResponseBadRequest(f"ValidationError: {err.message}")

        # Create new process instance
        new_process = cls.objects.create(
            name=slug,
            callback_url=callback_url,
            plugin=plugin
        )
        logger.info(f"Created process: {new_process}")

        # Start process
        new_process.start(payload)

        if new_process.errors:
            logger.error(f"Failed to start process {new_process}")
            errors = new_process.errors
            new_process.delete()
            return HttpResponseServerError(json.dumps(errors))

        logger.info(f"Started process: {new_process}")

        # return 202 with resource location in header
        response = HttpResponse(status=HTTPStatus.ACCEPTED)
        response['Location'] = f"/api/internal/process/{plugin_name}.{slug}/{new_process.pk}"
        return response

    properties = {}
    required = {}
    # if jsonschema provided, convert it to openapi
    if cls.input_schema:
        schema = convert(cls.input_schema)
        properties = schema.get('properties')
        required = schema.get('required')

    return swagger_auto_schema(
        method='post',
        responses={
            202: 'Process successfully started. Use the URL from the `Location` header in the response to get the status and outcome of the process.'
        },
        operation_description=f"Start a new governance process of type '{slug}'",
        manual_parameters=[openapi_community_header],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "callback_url": openapi.Schema(type=openapi.TYPE_STRING, description='URL to POST outcome to when process is completed'),
                **properties
            },
            required=required
        )
    )(create_process)


def decorated_perform_action_view(plugin_name, slug):
    cls = plugin_registry[plugin_name]
    meta = cls._action_registry[slug]

    @community_middleware
    @api_view(['POST'])
    def perform_action(request):
        """
        Perform an action on a platform
        """
        # 1. Look up plugin instance
        try:
            plugin = get_plugin_instance(plugin_name, request.community)
        except Exception as e:
            return HttpResponseBadRequest(e)

        action_function = getattr(plugin, meta.function_name)

        # 2. Validate input parameters
        payload = JSONParser().parse(request)
        parameters = payload.get('parameters')
        if meta.input_schema:
            try:
                jsonschema.validate(parameters, meta.input_schema)
            except jsonschema.exceptions.ValidationError as err:
                return HttpResponseBadRequest(f"ValidationError: {err.message}")

        # 3. Invoke action function
        try:
            user_id = payload.get('initiator', {}).get('user_id')
            # provider = payload.get('initiator', {}).get('provider')
            # TODO lookup user in metagov, find identity for this provider
            response = action_function(parameters, user_id)
        except ValueError as err:  # FIXME use custom err type
            return HttpResponseServerError(f"Error executing action: {err}")

        # 4. Validate response
        if meta.output_schema:
            try:
                jsonschema.validate(response, meta.output_schema)
            except jsonschema.exceptions.ValidationError as err:
                return HttpResponseBadRequest(f"ValidationError: {err.message}")

        # 5. Return response
        return JsonResponse(response)

    arg_dict = {
        'method': 'post',
        'operation_description': meta.description,
        'manual_parameters': [openapi_community_header],
    }
    if meta.input_schema:
        schema = convert(meta.input_schema)
        properties = {
            'parameters': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties=schema.get('properties', {}),
                required=schema.get('required', [])),
            'initiator': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description='Perform the action on behalf of this user. If not provided, or if plugin does not have sufficient access, the action will be performed by the system or bot user.',
                properties={'user_id': {'type': 'string', 'description': 'User identifier from the identity provider'},
                            'provider': {'type': 'string', 'description': 'Name of the identity provider'}})
        }

        arg_dict['request_body'] = openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={**properties}
        )

    if meta.output_schema:
        schema = convert(meta.output_schema)
        arg_dict['responses'] = {
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties=schema.get('properties', {})
            )
        }
    else:
        arg_dict['responses'] = {200: 'action was performed successfully'}
    return swagger_auto_schema(**arg_dict)(perform_action)


def jsonschema_to_parameters(schema):
    schema = convert(schema)
    properties = schema.get('properties', {})
    required = schema.get('required', [])
    parameters = []
    for (name, prop) in properties.items():
        param = openapi.Parameter(
            name=name, in_="query",
            description=prop.get('description'),
            type=prop.get('type'),
            required=name in required)
        parameters.append(param)
    return parameters


def get_plugin_instance(plugin_name, community):
    cls = plugin_registry.get(plugin_name)
    if not cls:
        raise Exception(f"Plugin '{plugin_name}' not registered")

    plugin = cls.objects.filter(name=plugin_name, community=community).first()
    if not plugin:
        raise Exception(
            f"Plugin '{plugin_name}' not enabled for community '{community.name}'")
    return plugin


def decorated_resource_view(plugin_name, slug):
    cls = plugin_registry[plugin_name]
    meta = cls._resource_registry[slug]

    @community_middleware
    @api_view(['GET'])
    def get_resource(request):
        # Look up plugin instance
        plugin = cls.objects.filter(
            name=plugin_name, community=request.community).first()
        if not plugin:
            return HttpResponseBadRequest(f"Plugin '{plugin_name}' not enabled for community '{request.community.name}'")

        parameters = request.GET.dict()  # doesnt support repeated params 'a=2&a=3'
        # Validate parameters
        if meta.input_schema:
            try:
                jsonschema.validate(parameters, meta.input_schema)
            except jsonschema.exceptions.ValidationError as err:
                return HttpResponseBadRequest(f"ValidationError: {err.message}")

        # Call the resource retrieval function
        function = getattr(plugin, meta.function_name)
        resource = function(parameters)

        # Validate resource
        if meta.output_schema:
            try:
                jsonschema.validate(resource, meta.output_schema)
            except jsonschema.exceptions.ValidationError as err:
                return HttpResponseBadRequest(f"ValidationError: {err.message}")
        return JsonResponse(resource)

    arg_dict = {
        'method': 'get',
        'operation_description': meta.description,
        'manual_parameters': [openapi_community_header],
    }
    if meta.input_schema:
        arg_dict['manual_parameters'].extend(
            jsonschema_to_parameters(meta.input_schema))
    if meta.output_schema:
        schema = convert(meta.output_schema)
        arg_dict['responses'] = {
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties=schema.get('properties', {})
            )
        }

    return swagger_auto_schema(**arg_dict)(get_resource)


@receiver(config_updated)
def constance_updated(sender, key, old_value, new_value, **kwargs):
    # TODO reload plugins ?
    logger.info(f"Config updated: {key}: {old_value} -> {new_value}")
