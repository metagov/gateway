from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.parsers import JSONParser
from rest_framework import status
from django.http import JsonResponse

from metagov.core import identity
from metagov.core.utils import get_plugin_instance
from metagov.core.models import Community


@api_view(["POST"])
def create_id(request):
    data = JSONParser().parse(request)
    try:
        params = {"community": Community.objects.get(slug=data["community_slug"]), "count": data.get("count", None)}
        new_id = identity.create_id(**identity.strip_null_values_from_dict(params))
        return JsonResponse(new_id, status=status.HTTP_201_CREATED, safe=False)
    except Exception as error:
        return JsonResponse(error, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def merge_ids(request):
    data = JSONParser().parse(request)
    try:
        identity.merge_ids(data["primary_instance_id"], data["secondary_instance_id"])
        return JsonResponse(status=status.HTTP_200_OK)
    except Exception as error:
        return JsonResponse(error, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def link_account(request):
    data = JSONParser().parse(request)
    # Validate that plugin is enabled for community
    _ = get_plugin_instance(
        data["platform_type"],
        Community.objects.get(slug=data["community_slug"]),
        community_platform_id=data.get("community_platform_id", None),
    )
    try:
        params = {
            "external_id": data["external_id"],
            "community": Community.objects.get(slug=data["community_slug"]),
            "platform_type": data["platform_type"],
            "platform_identifier": data["platform_identifier"],
            "community_platform_id": data.get("community_platform_id", None),
            "custom_data": data.get("custom_data", None),
            "link_type": data.get("link_type", None),
            "link_quality": data.get("link_quality", None),
        }
        account = identity.link_account(**identity.strip_null_values_from_dict(params))
        return JsonResponse(account.serialize(), status=status.HTTP_200_OK, safe=False)
    except Exception as error:
        return JsonResponse(error, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def unlink_account(request):
    data = JSONParser().parse(request)
    # Validate that plugin is enabled for community
    _ = get_plugin_instance(
        data["platform_type"],
        Community.objects.get(slug=data["community_slug"]),
        community_platform_id=data.get("community_platform_id", None),
    )
    try:
        params = {
            "community": Community.objects.get(slug=data["community_slug"]),
            "platform_type": data["platform_type"],
            "platform_identifier": data["platform_identifier"],
            "community_platform_id": data.get("community_platform_id", None),
        }
        account_deleted = identity.link_account(**identity.strip_null_values_from_dict(params))
        return JsonResponse(account_deleted, status=status.HTTP_200_OK, safe=False)
    except Exception as error:
        return JsonResponse(error, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def get_user(request):
    try:
        return JsonResponse(identity.get_user(request.GET.get("external_id")), status=status.HTTP_200_OK, safe=False)
    except Exception as error:
        return JsonResponse(error, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def get_users(request):
    community = Community.objects.get(slug=request.GET.get("community"))
    if request.GET.__contains__("platform_type"):
        # Validate that plugin is enabled for community
        _ = get_plugin_instance(
            request.GET.get("platform_type"),
            community,
            community_platform_id=request.GET.get("community_platform_id", None),
        )
    try:
        params = {
            "community": community,
            "platform_type": request.GET.get("platform_type", None),
            "community_platform_id": request.GET.get("community_platform_id", None),
            "link_type": request.GET.get("link_type", None),
            "link_quality": request.GET.get("link_quality", None),
            "platform_identifier": request.GET.get("platform_identifier", None),
        }
        user_data = identity.get_users(**identity.strip_null_values_from_dict(params))
        return JsonResponse(user_data, status=status.HTTP_200_OK, safe=False)
    except Exception as error:
        return JsonResponse(error, status=status.HTTP_400_BAD_REQUEST, safe=False)


@api_view(["GET"])
def filter_users_by_account(request):
    community = Community.objects.get(slug=request.GET.get("community"))
    if request.GET.__contains__("platform_type"):
        # Validate that plugin is enabled for community
        _ = get_plugin_instance(
            request.GET.get("platform_type"),
            community,
            community_platform_id=request.GET.get("community_platform_id", None),
        )
    try:
        params = {
            "external_id_list": request.GET.get("external_id_list"),
            "community": community,
            "platform_type": request.GET.get("platform_type", None),
            "community_platform_id": request.GET.get("community_platform_id", None),
            "link_type": request.GET.get("link_type", None),
            "link_quality": request.GET.get("link_quality", None),
        }
        user_data = identity.filter_users_by_account(**identity.strip_null_values_from_dict(params))
        return JsonResponse(user_data, status=status.HTTP_200_OK, safe=False)
    except Exception as error:
        return JsonResponse(error, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def get_linked_account(request):
    try:
        params = {
            "external_id": request.GET.get("external_id"),
            "platform_type": request.GET.get("platform_type"),
            "community_platform_id": request.GET.get("community_platform_id", None),
        }
        user_data = identity.get_linked_account(**identity.strip_null_values_from_dict(params))
        return JsonResponse(user_data, status=status.HTTP_200_OK, safe=False)
    except Exception as error:
        return JsonResponse(error, status=status.HTTP_400_BAD_REQUEST)