from drf_yasg import openapi
from metagov.core.middleware import COMMUNITY_HEADER


class Tags(object):
    GOVERNANCE_PROCESS = "Governance Processes"
    PUBLIC_ACTION = "Actions (Public)"
    ACTION = "Actions"
    COMMUNITY = "Community Configuration"


community_header = openapi.Parameter(
    COMMUNITY_HEADER, openapi.IN_HEADER, required=True, type=openapi.TYPE_STRING, description="Unique community slug"
)

community_name_in_path = openapi.Parameter(
    "name", openapi.IN_PATH, required=True, type=openapi.TYPE_STRING, description="Unique community slug"
)

community_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "name": openapi.Schema(type=openapi.TYPE_STRING, description="Unique community slug"),
        "readable_name": openapi.Schema(type=openapi.TYPE_STRING, description="Human-readable community name"),
        "plugins": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            description="List of enabled plugins and their configs",
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

plugin_schemas = {
    "method": "get",
    "operation_id": "Get plugin configuration schemas in jsonschema format",
    "tags": [Tags.COMMUNITY],
}

list_hooks = {
    "method": "get",
    "operation_id": "List community webhook receiver URLs",
    "responses": {
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "hooks": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                )
            },
        ),
    },
    "manual_parameters": [community_name_in_path],
    "tags": [Tags.COMMUNITY],
}

list_actions = {
    "method": "get",
    "operation_id": "List available actions",
    "responses": {
        200: openapi.Schema(
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
        ),
    },
    "manual_parameters": [community_name_in_path],
    "tags": [Tags.COMMUNITY],
}

list_processes = {
    "method": "get",
    "operation_id": "List available governance processes",
    "responses": {
        200: openapi.Schema(
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
        ),
    },
    "manual_parameters": [community_name_in_path],
    "tags": [Tags.COMMUNITY],
}

list_events = {
    "method": "get",
    "operation_id": "List available events",
    "responses": {
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "events": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "type": openapi.Schema(type=openapi.TYPE_STRING),
                            "source": openapi.Schema(type=openapi.TYPE_STRING),
                            "schema": openapi.Schema(type=openapi.TYPE_OBJECT),
                        },
                    ),
                )
            },
        ),
    },
    "manual_parameters": [community_name_in_path],
    "tags": [Tags.COMMUNITY],
}