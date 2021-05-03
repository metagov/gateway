from drf_yasg import openapi

community_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "name": openapi.Schema(type=openapi.TYPE_STRING, description="Unique community slug"),
        "readable_name": openapi.Schema(type=openapi.TYPE_STRING, description="Human-readable community name"),
        "plugins": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            description="List of activated plugins and their configs",
            items=openapi.Items(
                type=openapi.TYPE_OBJECT,
                properties={
                    "name": openapi.Schema(type=openapi.TYPE_STRING, description="plugin name"),
                    "config": openapi.Schema(type=openapi.TYPE_OBJECT, description="plugin config"),
                },
            ),
        ),
    },
)

action_list_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "actions": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(
                type=openapi.TYPE_OBJECT,
                properties={
                    "id": openapi.Schema(type=openapi.TYPE_STRING),
                    "description": openapi.Schema(type=openapi.TYPE_STRING),
                    "parameters_schema": openapi.Schema(type=openapi.TYPE_OBJECT),
                    "response_schema": openapi.Schema(type=openapi.TYPE_OBJECT),
                },
            ),
        )
    },
)

process_list_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "processes": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(
                type=openapi.TYPE_OBJECT,
                properties={
                    "id": openapi.Schema(type=openapi.TYPE_STRING),
                    "description": openapi.Schema(type=openapi.TYPE_STRING),
                    "parameters_schema": openapi.Schema(type=openapi.TYPE_OBJECT),
                    "response_schema": openapi.Schema(type=openapi.TYPE_OBJECT),
                },
            ),
        )
    },
)


class Tags(object):
    GOVERNANCE_PROCESS = "Governance Processes"
    PUBLIC_ACTION = "Actions (Public)"
    ACTION = "Actions"
    COMMUNITY = "Community Configuration"
