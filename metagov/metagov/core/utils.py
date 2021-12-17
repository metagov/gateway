import json
import logging
import random
import jsonschema

logger = logging.getLogger(__name__)

internal_path = "api/internal"


def plugin_uses_webhooks(cls):
    return cls._webhook_receiver_function is not None


class SaferDraft7Validator(jsonschema.Draft7Validator):
    META_SCHEMA = {**jsonschema.Draft7Validator.META_SCHEMA, "additionalProperties": False}


def generate_nonce(length=8):
    """Generate pseudorandom number."""
    return "".join([str(random.randint(0, 9)) for i in range(length)])


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


def get_action_schemas(cls):
    actions = []
    for (name, meta) in cls._action_registry.items():
        actions.append(
            {
                "id": f"{cls.name}.{name}",
                "description": meta.description,
                "parameters_schema": meta.input_schema,
                "response_schema": meta.output_schema,
            }
        )
    return actions


def get_event_schemas(cls):
    result = []
    for event in cls._event_schemas:
        if event.get("type"):
            result.append({"event_type": event["type"], "source": cls.name, "schema": event.get("schema")})

    return result


def get_process_schemas(cls):
    processes = []
    for (name, process_cls) in cls._process_registry.items():
        processes.append(
            {
                "id": f"{cls.name}.{name}",
                "description": process_cls.description,
                "parameters_schema": process_cls.input_schema,
                "response_schema": process_cls.outcome_schema,
            }
        )
    return processes


def validate_and_fill_defaults(values, schema):
    from metagov.core.validators import DefaultValidatingDraft7Validator

    # this mutates `plugin_config` by filling in default values from schema
    # raises jsonschema.exceptions.ValidationError
    DefaultValidatingDraft7Validator(schema).validate(values)


def create_or_update_plugin(plugin_name, plugin_config, community):
    from metagov.core.plugin_manager import plugin_registry

    cls = plugin_registry.get(plugin_name)
    if not cls:
        raise ValueError(f"No such plugin registered: {plugin_name}")

    if cls.config_schema:
        validate_and_fill_defaults(plugin_config, cls.config_schema)

    community_platform_id = None
    if cls.community_platform_id_key:
        community_platform_id = str(plugin_config.get(cls.community_platform_id_key))

    try:
        plugin = cls.objects.get(name=plugin_name, community=community, community_platform_id=community_platform_id)
    except cls.DoesNotExist:
        inst = cls.objects.create(
            name=plugin_name, community=community, config=plugin_config, community_platform_id=community_platform_id
        )
        logger.info(f"Created plugin '{inst}'")
        inst.initialize()
        return (inst, True)
    else:
        if plugin.config != plugin_config:
            # TODO what happens to pending processes?
            logger.info(f"Destroying and re-creating '{plugin}' to apply config change")
            plugin.delete()
            inst = cls.objects.create(
                name=plugin_name,
                community=community,
                config=plugin_config,
                community_platform_id=community_platform_id,
            )
            inst.initialize()
            return (inst, True)

        logger.info(f"Not updating '{plugin}', no change in config.")
        return (plugin, False)


def get_plugin_instance(plugin_name, community, community_platform_id=None):
    """
    Get a plugin instance. Returns the proxy instance (e.g. "Slack" or "OpenCollective"), not the Plugin instance.
    """
    try:
        return community.get_plugin(plugin_name, community_platform_id)
    except ValueError:
        raise ValidationError(f"Plugin '{plugin_name}' not found")
    except Plugin.DoesNotExist:
        extra = f"with community_platform_id '{community_platform_id}'" if community_platform_id else ""
        raise ValidationError(f"Plugin '{plugin_name}' {extra} not enabled for community '{community}'")
    except Plugin.MultipleObjectsReturned:
        raise ValidationError(
            f"Plugin '{plugin_name}' has multiple instances for community '{community}'. Please specify community_platform_id."
        )


def get_configuration(config_name, **kwargs):

    # if multi driver functionality is on, use httpwrapper's version of get_configuration
    from django.conf import settings
    if hasattr(settings, "MULTI_DRIVER") and settings.MULTI_DRIVER:
        from metagov.httpwrapper.utils import get_configuration as multidriver_get_configuration
        return multidriver_get_configuration(config_name, **kwargs)

    # otherwise just get from environment
    from metagov.settings import TESTING
    default_val = TESTING if TESTING else None

    return env(config_name, default=default_val)


def set_configuration(config_name, config_value, **kwargs):
    # TODO: implement this as a helper method for single-driver apps
    pass


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
