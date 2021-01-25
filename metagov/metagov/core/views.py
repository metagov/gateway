from django.http import HttpResponse, HttpResponseBadRequest
from metagov.core.plugins import ResourceProvider

def index(request):
    return HttpResponse("hello world🌈")

def get_resource(request, slug):
    """
    API endpoint that allows retrieving a resource defined by a plugins.
    """
    if request.method != 'GET':
        return HttpResponseBadRequest("Resource endpoint only supports GET")
    plugins = [p for p in ResourceProvider.plugins if p.slug == slug]
    if not plugins:
        return HttpResponseBadRequest(f"No plugin found with slug '{slug}'")
    querydict = request.GET
    inst = plugins[0]()
    return inst.retrieve_resource(querydict)
