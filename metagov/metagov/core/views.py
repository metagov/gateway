import json
import logging
from http import HTTPStatus

from django.core.exceptions import ValidationError
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseNotFound, JsonResponse, QueryDict)
from django.shortcuts import render
from django.template import loader
from django.views.decorators.csrf import csrf_exempt
from metagov.core.models import GovernanceProcess, GovernanceProcessSerializer
from metagov.core.plugin_models import (GovernanceProcessProvider,
                                        function_registry, listener_registry)
from rest_framework.decorators import api_view

logger = logging.getLogger('django')


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

    # FIXME middleware to validate input/output?
    return item.get('function')(request.GET)


@api_view(['POST'])
def create_process(request):
    """
    Start new governance process
    """
    payload = request_body(request)
    if not payload:
        logger.error("no payload")
        return HttpResponse()

    process_name = payload.get('process_name')
    callback_url = payload.get('callback_url')
    new_process = GovernanceProcess(
        name=process_name, callback_url=callback_url)
    try:
        new_process.full_clean()
    except ValidationError as e:
        logger.error(e)
        return HttpResponseBadRequest(e)

    new_process.save()  # save to create DataStore
    new_process.start(payload)
    logger.info(f"Started '{process_name}' process with id {new_process.pk}")

    # return 202 with resource location in header
    response = HttpResponse(status=HTTPStatus.ACCEPTED)
    response['Location'] = f"/api/internal/process/{new_process.pk}"
    return response


@api_view(['GET', 'DELETE'])
def get_process(request, process_id):
    """
    Get or delete governance process
    """
    try:
        process = GovernanceProcess.objects.get(pk=process_id)
    except GovernanceProcess.DoesNotExist:
        return HttpResponseNotFound()

    if request.method == 'DELETE':
        process.cancel()
        # process.delete()
        return HttpResponse()

    serializer = GovernanceProcessSerializer(process)
    logger.info(f"Returning serialized process: {serializer.data}")
    return JsonResponse(serializer.data)


@csrf_exempt
def receive_webhook(request, slug):
    """
    API endpoint for receiving webhook requests from external services
    """

    query_dict = request_body(request)
    if not query_dict:
        return HttpResponse()

    listener = listener_registry.get_function(slug)
    if listener:
        listener.get('function')(request)

    active_processes = GovernanceProcess.objects.filter(name=slug)

    logger.info(
        f"invoking handlers for {active_processes.count()} active processes")
    logger.info(query_dict)
    for p in active_processes:
        p.handle_webhook(query_dict)

    return HttpResponse("ok")


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
