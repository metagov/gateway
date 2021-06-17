from rest_framework.exceptions import APIException


class PluginErrorInternal(APIException):
    pass


class PluginAuthError(APIException):
    default_code = "server_error"
