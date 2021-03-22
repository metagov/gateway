from enum import Enum

import jsonschema


class FunctionType(Enum):
    RESOURCE = "resource"
    ACTION = "action"


plugin_registry = {}


class SaferDraft7Validator(jsonschema.Draft7Validator):
    META_SCHEMA = {**jsonschema.Draft7Validator.META_SCHEMA,
                   "additionalProperties": False}


def plugin(cls):
    """
    Plugin class decorator
    """
    if not cls._meta.proxy:
        raise Exception("Plugins must by proxy models")

    if cls.config_schema:
        SaferDraft7Validator.check_schema(cls.config_schema)
    cls._resource_registry = {}
    cls._action_registry = {}
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
