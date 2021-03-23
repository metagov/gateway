from enum import Enum

from metagov.core.utils import SaferDraft7Validator

class FunctionType(Enum):
    RESOURCE = "resource"
    ACTION = "action"


plugin_registry = {}

def plugin(cls):
    """
    Plugin model decorator
    """
    if not cls._meta.proxy:
        raise Exception(f"Failed to register {cls.name}: must be a Django proxy model")

    if cls.config_schema:
        SaferDraft7Validator.check_schema(cls.config_schema)
    cls._resource_registry = {}
    cls._action_registry = {}
    cls._process_registry = {}

    plugin_registry[cls.name] = cls
    for methodname in dir(cls):
        method = getattr(cls, methodname)
        if hasattr(method, '_meta'):
            meta = method._meta
            assert(meta.function_name == methodname)
            if meta.type is FunctionType.ACTION:
                cls._action_registry[meta.slug] = method._meta
            elif meta.type is FunctionType.RESOURCE:
                cls._resource_registry[meta.slug] = method._meta
    return cls

def governance_process(cls):
    """
    Process model decorator
    """
    if not cls._meta.proxy:
        raise Exception(f"Failed to register {cls.name}: must be a Django proxy model")

    if not plugin_registry.get(cls.plugin_name):
        raise Exception(f"Failed to register {cls.name}: No such plugin '{cls.plugin_name}'. Plugin must be declared before process.")

    if cls.input_schema:
        SaferDraft7Validator.check_schema(cls.input_schema)

    r = plugin_registry[cls.plugin_name]
    r._process_registry[cls.name] = cls

class ResourceFunctionMeta:
    def __init__(self, slug, function_name, description, input_schema, output_schema):
        self.type = FunctionType.RESOURCE
        self.slug = slug
        self.function_name = function_name
        self.description = description
        self.input_schema = input_schema
        self.output_schema = output_schema


class ActionFunctionMeta:
    def __init__(self, slug, function_name, description, input_schema, output_schema):
        self.type = FunctionType.ACTION
        self.slug = slug
        self.function_name = function_name
        self.description = description
        self.input_schema = input_schema
        self.output_schema = output_schema


def resource(slug, description, input_schema=None, output_schema=None):
    """
    Resource function decorator
    """
    def wrapper(function):
        if input_schema:
            SaferDraft7Validator.check_schema(input_schema)
        if output_schema:
            SaferDraft7Validator.check_schema(output_schema)

        function._meta = ResourceFunctionMeta(
            slug=slug,
            function_name=function.__name__,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema
        )
        return function
    return wrapper


def action(slug, description, input_schema=None, output_schema=None):
    """
    Action function decorator
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
            output_schema=output_schema
        )
        return function
    return wrapper
