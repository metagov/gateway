from metagov.core.utils import SaferDraft7Validator

plugin_registry = {}


class Parameters:
    def __init__(self, values={}, schema=None):
        if schema:
            from metagov.core.utils import validate_and_fill_defaults

            validate_and_fill_defaults(values, schema)

        for k, v in values.items():
            setattr(self, k, v)

        setattr(self, "_json", values)

        if schema:
            for field in schema.get("properties").keys():
                if not values.get(field):
                    setattr(self, field, None)


class VotingStandard:
    INPUT_PARAMETERS = {
        "title": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
        "details": {"type": "string"},
        "closing_at": {"type": "string", "format": "date"},
    }

    @staticmethod
    def create_input_schema(include=None, exclude=None, extra_properties=None, required=None):
        properties = {}

        if include and len(include) > 0:
            properties = {k: VotingStandard.INPUT_PARAMETERS[k] for k in include}
        else:
            properties = VotingStandard.INPUT_PARAMETERS

        if exclude:
            for prop in exclude:
                properties.pop(prop, None)

        if extra_properties:
            for (prop, definition) in extra_properties.items():
                properties[prop] = definition

        schema = {"properties": properties}
        if required:
            schema["required"] = [prop for prop in required if prop in properties.keys()]

        return schema


class Registry:
    class EventProducerMeta:
        def __init__(self, function_name, event_schemas):
            self.function_name = function_name
            self.event_schemas = event_schemas

    class ActionFunctionMeta:
        def __init__(self, slug, function_name, description, input_schema, output_schema, is_public):
            self.slug = slug
            self.function_name = function_name
            self.description = description
            self.input_schema = input_schema
            self.output_schema = output_schema
            self.is_public = is_public

    @staticmethod
    def _validate_proxy_model(cls):
        if not isinstance(cls.name, str):
            raise Exception(f"Failed to register model, missing name attribute")
        if not hasattr(cls, "_meta") or not cls._meta.proxy:
            raise Exception(f"Failed to register {cls.name}: must be a Django proxy model")

    @staticmethod
    def plugin(cls):
        """Use this decorator on a subclass of :class:`~metagov.core.models.Plugin` to register it as a plugin."""
        Registry._validate_proxy_model(cls)
        if cls.config_schema:
            SaferDraft7Validator.check_schema(cls.config_schema)

        cls._action_registry = {}
        cls._process_registry = {}
        cls._task_function = None
        cls._webhook_receiver_function = None
        cls._event_schemas = []

        plugin_registry[cls.name] = cls
        for methodname in dir(cls):
            method = getattr(cls, methodname)
            if hasattr(method, "_meta"):
                meta = method._meta
                assert meta.function_name == methodname
                if meta.slug in cls._action_registry:
                    raise Exception(f"'{cls.name}.{meta.slug}' already registered")
                cls._action_registry[meta.slug] = method._meta
            elif hasattr(method, "_meta_task"):
                cls._task_function = methodname
                cls._event_schemas.extend(method._meta_task.event_schemas)
            elif hasattr(method, "_meta_webhook_receiver"):
                cls._webhook_receiver_function = methodname
                cls._event_schemas.extend(method._meta_webhook_receiver.event_schemas)
        return cls

    @staticmethod
    def governance_process(cls):
        """Use this decorator on a subclass of :class:`~metagov.core.models.GovernanceProcess` to register it as a governance process."""
        Registry._validate_proxy_model(cls)

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

        setattr(cls, "plugin_inst", property(get_plugin))
        return cls

    @staticmethod
    def event_producer_task(event_schemas=[]):
        """Use this decorator on a method of a registered :class:`~metagov.core.models.Plugin` to register a task that sends Events to the Driver."""

        def wrapper(function):
            function._meta_task = Registry.EventProducerMeta(
                function_name=function.__name__,
                event_schemas=event_schemas,
            )
            return function

        return wrapper

    @staticmethod
    def webhook_receiver(event_schemas=[]):
        """Use this decorator on a method of a registered :class:`~metagov.core.models.Plugin` to register a webhook receiver. Webhook requests recieved for this plugin instance will be passed to the registered method."""

        def wrapper(function):
            function._meta_webhook_receiver = Registry.EventProducerMeta(
                function_name=function.__name__,
                event_schemas=event_schemas,
            )
            return function

        return wrapper

    @staticmethod
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

            function._meta = Registry.ActionFunctionMeta(
                slug=slug,
                function_name=function.__name__,
                description=description,
                input_schema=input_schema,
                output_schema=output_schema,
                is_public=is_public,
            )
            return function

        return wrapper


class AuthorizationType:
    USER_LOGIN = "user"
    APP_INSTALL = "app"
