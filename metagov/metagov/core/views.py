import json
import logging
from http import HTTPStatus

from django.core.exceptions import ValidationError
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseNotFound, JsonResponse, QueryDict)
from django.shortcuts import render
from django.template import loader
from django.views.decorators.csrf import csrf_exempt
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from metagov.core.models import GovernanceProcess, GovernanceProcessSerializer
from metagov.core.plugin_models import (GovernanceProcessProvider,
                                        function_registry, listener_registry)
from rest_framework.decorators import api_view
from rest_framework.schemas import AutoSchema
from rest_framework.views import APIView

logger = logging.getLogger('django')

my_plugin_input_fields = {
    "type": openapi.TYPE_OBJECT,
    "title": "Loomio input",
    "properties": {
        "title": openapi.Schema(
            title="Poll Title",
            type=openapi.TYPE_STRING,
        ),
        "closes_at": openapi.Schema(
            title="Poll close date",
            type=openapi.TYPE_STRING,
        ),
    },
    "required": ["title", "closes_at"],
}


def index(request):
    registered_resource_retrievals = [
        (k, v['description']) for k, v in function_registry.registry.items()]
    registered_governance_processes = list(
        GovernanceProcessProvider.plugins.keys())
    context = {
        'registered_resource_retrievals': registered_resource_retrievals,
        'registered_governance_processes': registered_governance_processes
    }
    return render(request, 'index.html', context)


@api_view(['GET'])
def get_resource(request, resource_name):
    """
    API endpoint for retrieving a resource defined in a plugin
    """
    if request.method != 'GET':
        return HttpResponseBadRequest("Resource endpoint only supports GET")

    item = function_registry.get_function(resource_name)
    if item is None:
        return HttpResponseBadRequest(f"Resource retrieval function {resource_name} not registered")

    # TODO: validate query params; swagger docs
    return item.get('function')(request.GET)


def create_process_endpoint(process_name):
    @api_view(['POST'])
    def create_process(request):
        """
        Start new governance process
        """
        payload = request_body(request)

        if not payload:
            logger.error("no payload")
            return HttpResponse()

        new_process = GovernanceProcess(
            name=process_name, callback_url=payload.get('callback_url'))
        try:
            new_process.full_clean()
        except ValidationError as e:
            logger.error(e)
            return HttpResponseBadRequest(e)

        new_process.save()  # save to create DataStore

        # TODO: validate payload (plugin author implement serializer?)
        new_process.start(payload)
        if new_process.errors:
            logger.info("failed to start process")
            new_process.delete()
            return HttpResponseServerError(json.dumps(new_process.errors))

        logger.info(
            f"Started '{process_name}' process with id {new_process.pk}")

        # return 202 with resource location in header
        response = HttpResponse(status=HTTPStatus.ACCEPTED)
        response['Location'] = f"/api/internal/process/{process_name}/{new_process.pk}"
        return response

    return create_process


@swagger_auto_schema(method='delete',
                     operation_description="Cancel governance process")
@swagger_auto_schema(method='get',
                     operation_description="Get status of governance process",
                     responses={
                            200: openapi.Response(
                                'Current process record. Check the `status` field to see if the process has completed. If the `errors` field has data, the process failed.', GovernanceProcessSerializer),
                            404: 'Process not found'})
@api_view(['GET', 'DELETE'])
def get_process(request, process_id):
    try:
        process = GovernanceProcess.objects.get(pk=process_id)
    except GovernanceProcess.DoesNotExist:
        return HttpResponseNotFound()

    if request.method == 'DELETE':
        process.cancel()
        # actually delete?
        return HttpResponse(status=204)

    serializer = GovernanceProcessSerializer(process)
    logger.info(f"Returning serialized process: {serializer.data}")
    return JsonResponse(serializer.data)


@csrf_exempt
def receive_webhook(request, slug):
    """
    API endpoint for receiving webhook requests from external services
    """
    logger.info(request.body)

    listener = listener_registry.get_function(slug)
    if listener:
        listener.get('function')(request)

    active_processes = GovernanceProcess.objects.filter(name=slug)
    if active_processes.count() > 0:
        logger.info(
            f"invoking handlers for {active_processes.count()} active processes")
        for p in active_processes:
            p.handle_webhook(request)

    return HttpResponse()


def request_body(request):
    if request.POST:
        return request.POST
    if len(request.body) > 0:
        body_data = {}
        try:
            body_data = json.loads(request.body)
        except ValueError:
            logger.error("unable to decode webhook body")
            return HttpResponse("ok")
        query_dict = QueryDict('', mutable=True)
        query_dict.update(body_data)
        return query_dict

    return None


def decorated_create_process_view(slug):
    """
    Decorate the `create_process_endpoint` view with swagger schema properties defined by the plugin author

    TODO: include schemas for outcome too, not just input.
    """
    cls = GovernanceProcessProvider.plugins.get(slug)
    schema = cls.input_schema
    properties = schema.get('properties')
    required = schema.get('required')

    view = create_process_endpoint(slug)

    return swagger_auto_schema(
        method='post',
        responses={
            202: 'Process successfully started. Use the URL from the `Location` header in the response to get the status and outcome of the process.'
        },
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            title="input",
            properties={
                "callback_url": openapi.Schema(type=openapi.TYPE_STRING, description='URL to POST outcome to when process is completed'),
                **properties
            },
            required=required
        )
    )(view)
