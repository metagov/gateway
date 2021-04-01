from django.http import HttpResponseBadRequest
from metagov.core.models import Community
from drf_yasg import openapi

COMMUNITY_HEADER = "X-Metagov-Community"


class CommunityMiddleware:
    """
    Middleware for attaching Community to request object
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, *view_args, **view_kwargs):
        community_name = request.headers.get(COMMUNITY_HEADER)
        if not community_name:
            return HttpResponseBadRequest(f"Missing required header '{COMMUNITY_HEADER}'")
        try:
            community = Community.objects.get(name=community_name)
        except Community.DoesNotExist:
            return HttpResponseBadRequest(f"Community '{community_name}' not found")
        request.community = community


openapi_community_header = openapi.Parameter(
    COMMUNITY_HEADER, openapi.IN_HEADER, required=True, type=openapi.TYPE_STRING, description="Unique community slug"
)
