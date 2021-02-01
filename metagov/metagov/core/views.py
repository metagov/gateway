from django.http import HttpResponse, HttpResponseBadRequest
from metagov.core.plugin_models import GovernanceProcessProvider, function_registry
from metagov.core.models import GovernanceProcess, DataStore
from django.views.decorators.csrf import csrf_exempt
from django.http import QueryDict
import logging
import json

logger = logging.getLogger('django')


def index(request):
    return HttpResponse("hello world🌈")


def get_resource(request, slug, resource_name):
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


def start_governance_process(request, slug):
    """
    API endpoint for kicking off a governance process defined in a plugin
    """
    new_process = GovernanceProcess(plugin_name=slug)
    new_process.save()
    logger.info(f"Created new {slug} process with id {new_process.pk}")

    querydict = request.POST or request.GET
    # FIXME middleware to validate input/output?
    result = new_process.start(querydict)
    logger.info(result)
    return HttpResponse(result.toJSON())


@csrf_exempt
def receive_webhook(request, slug):
    """
    API endpoint for receiving webhook requests from external services
    """

    if request.POST or request.GET:
        query_dict = request.POST or request.GET
    elif len(request.body) > 0:
        # FIXME why is loomio request body not being parsed into django query dict?
        body_data = {}
        try:
            body_data = json.loads(request.body)
        except Exception as e:
            logger.error("unable to decode webhook body")
            return HttpResponse("ok")
        query_dict = QueryDict('', mutable=True)
        query_dict.update(body_data)
    else:
        logger.info("no webhook request body")
        return HttpResponse("ok")

    active_processes = GovernanceProcess.objects.filter(plugin_name=slug)

    logger.info(
        f"Received webhook at '{slug}'. Found {active_processes.count()} active processes. Invoking handlers..")
    logger.info(query_dict)
    for p in active_processes:
        p.handle_webhook(query_dict)

    return HttpResponse("ok")
