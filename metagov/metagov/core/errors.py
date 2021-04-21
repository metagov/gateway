"""
TODO: define more error types for other status codes, so plugins can use them? Or just
tell plugin authors to use APIExeption and its subclasses that are provided by DRF.
"""

from rest_framework.exceptions import APIException


class PluginErrorInternal(APIException):
    pass
