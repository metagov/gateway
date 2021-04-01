import json

import jsonschema
from drf_yasg import openapi
from jsonschema_to_openapi.convert import convert

internal_path = "api/internal"


def construct_action_url(plugin_name: str, slug: str, is_public=False) -> str:
    if is_public:
        return f"api/action/{plugin_name}.{slug}"
    return f"{internal_path}/action/{plugin_name}.{slug}"


def construct_process_url(plugin_name: str, slug: str) -> str:
    return f"{internal_path}/process/{plugin_name}.{slug}"


class SaferDraft7Validator(jsonschema.Draft7Validator):
    META_SCHEMA = {**jsonschema.Draft7Validator.META_SCHEMA, "additionalProperties": False}


def json_schema_to_openapi_object(json_schema):
    schema = convert(json_schema)
    return openapi.Schema(
        type=openapi.TYPE_OBJECT, properties=schema.get("properties", {}), required=schema.get("required", [])
    )


def restruct(d):
    for k in d:
        # convert value if it's valid json
        if isinstance(d[k], list):
            v = d[k]
            try:
                d[k] = json.loads(v[0])
            except ValueError:
                d[k] = v[0]

        # step into dictionary objects to convert string digits to integer
        if isinstance(d[k], dict):
            restruct(d[k])
        else:
            try:
                d[k] = int(d[k])
            except ValueError:
                d[k] = d[k]


# def jsonschema_to_parameters(schema):
#     #arg_dict["manual_parameters"].extend(jsonschema_to_parameters(meta.input_schema
#     schema = convert(schema)
#     properties = schema.get("properties", {})
#     required = schema.get("required", [])
#     parameters = []
#     for (name, prop) in properties.items():
#         param = openapi.Parameter(
#             name=name,
#             in_="query",
#             description=prop.get("description"),
#             type=prop.get("type"),
#             required=name in required,
#         )
#         parameters.append(param)
#     return parameters
