from enum import Enum

from metagov.core.utils import SaferDraft7Validator

plugin_registry = {}


def validate_proxy_model(cls):
    if not isinstance(cls.name, str):
        raise Exception(f"Failed to register model, missing name attribute")
    if not hasattr(cls, "_meta") or not cls._meta.proxy:
        raise Exception(f"Failed to register {cls.name}: must be a Django proxy model")


def plugin(cls):
    """Use this decorator on a sublcass of :class:`~metagov.core.models.Plugin` to register it as a plugin."""
    validate_proxy_model(cls)
    if cls.config_schema:
        SaferDraft7Validator.check_schema(cls.config_schema)

    cls._action_registry = {}
    cls._process_registry = {}

    plugin_registry[cls.name] = cls
    for methodname in dir(cls):
        method = getattr(cls, methodname)
        if hasattr(method, "_meta"):
            meta = method._meta
            assert meta.function_name == methodname
            if meta.slug in cls._action_registry:
                raise Exception(f"'{cls.name}.{meta.slug}' already registered")
            cls._action_registry[meta.slug] = method._meta
    return cls


def governance_process(cls):
    """Use this decorator on a sublcass of :class:`~metagov.core.models.GovernanceProcess` to register it as a governance process."""
    validate_proxy_model(cls)

    if not hasattr(cls, "plugin_name"):
        raise Exception(f"Failed to register {cls.name}: Missing plugin name")
    if not plugin_registry.get(cls.plugin_name):
        raise Exception(
            f"Failed to register {cls.name}: No such plugin '{cls.plugin_name}'. Plugin must be declared before process."
        )

    if cls.input_schema:
        SaferDraft7Validator.check_schema(cls.input_schema)

    plugin_cls = plugin_registry[cls.plugin_name]
    plugin_cls._process_registry[cls.name] = cls

    # add function to get plugin proxy instance, so process can invoke proxy-specific functions
    def get_plugin(self):
        try:
            return plugin_cls.objects.get(pk=self.plugin.pk)
        except plugin_cls.DoesNotExist:
            return None

    cls.add_to_class("get_plugin", get_plugin)
    return cls


class ActionFunctionMeta:
    def __init__(self, slug, function_name, description, input_schema, output_schema, is_public):
        self.slug = slug
        self.function_name = function_name
        self.description = description
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.is_public = is_public


def action(slug, description, input_schema=None, output_schema=None, is_public=False):
    """Use this decorator on a method of a registered :class:`~metagov.core.models.Plugin` to register an action endpoint.

    Metagov will expose the decorated function at endpoint ``/action/<plugin-name>.<slug>``

    :param str slug: action slug
    :param str description: action description
    :param obj input_schema: jsonschema defining the input parameter object, optional
    :param obj output_schema: jsonschema defining the response object, optional
    """

    def wrapper(function):
        if input_schema:
            SaferDraft7Validator.check_schema(input_schema)
        if output_schema:
            SaferDraft7Validator.check_schema(output_schema)

        function._meta = ActionFunctionMeta(
            slug=slug,
            function_name=function.__name__,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            is_public=is_public,
        )
        return function

    return wrapper
