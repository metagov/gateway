import jsonschema

internal_path = "api/internal"


def construct_action_url(plugin_name: str, slug: str) -> str:
    return f"{internal_path}/action/{plugin_name}.{slug}"


def construct_resource_url(plugin_name: str, slug: str) -> str:
    return f"{internal_path}/resource/{plugin_name}.{slug}"


def construct_process_url(plugin_name: str, slug: str) -> str:
    return f"{internal_path}/process/{plugin_name}.{slug}"


class SaferDraft7Validator(jsonschema.Draft7Validator):
    META_SCHEMA = {**jsonschema.Draft7Validator.META_SCHEMA, "additionalProperties": False}
