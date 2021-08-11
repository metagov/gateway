class AuthorizationType:
    USER_LOGIN = "user"
    APP_INSTALL = "app"


class Parameters:
    def __init__(self, values={}, schema=None):
        for k, v in values.items():
            setattr(self, k, v)

        setattr(self, "_json", values)

        if schema:
            for field in schema.get("properties").keys():
                if not hasattr(self, field):
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
