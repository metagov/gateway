import base64
import hmac
import json
import logging
import urllib
import random
from hashlib import sha256

import requests
from django.conf import settings
from django.contrib.auth.models import User
from social_core.backends.base import BaseAuth

logger = logging.getLogger('django')


def generate_nonce(length=8):
    return ''.join([str(random.randint(0, 9)) for i in range(length)])


class DiscourseSSOAuth(BaseAuth):
    name = 'discourse'

    def auth_url(self):
        payload = f"nonce={generate_nonce()}&return_sso_url={self.redirect_uri}"
        base64Payload = base64.b64encode(
            payload.encode('utf-8')).decode('utf-8')
        payloadSignature = hmac.new(settings.DISCOURSE_SSO_SECRET.encode('utf-8'), base64Payload.encode('utf-8'),
                                    sha256).hexdigest()
        encodedParams = urllib.parse.urlencode(
            {'sso': base64Payload, 'sig': payloadSignature})
        return f"{settings.DISCOURSE_URL}/session/sso_provider?{encodedParams}"

    def get_user_id(self, details, response):
        obj = {k.decode('utf-8'): v.decode('utf-8') for k, v in response}
        return obj['email']

    def get_user_details(self, response):
        obj = {k.decode('utf-8'): v.decode('utf-8') for k, v in response}
        return {
            'username': obj.get('username'),
            'email': obj.get('email'),
            'name': obj.get('name'),
            # 'groups': obj.get('groups', '').split(','),
            'is_staff': obj.get('admin') == 'true' or obj.get('moderator') == 'true',
            'is_superuser': obj.get('admin') == 'true',
        }

    def auth_complete(self, request, *args, **kwargs):
        ssoParams = request.GET.get('sso')
        ssoSignature = request.GET.get('sig')
        paramSignature = hmac.new(settings.DISCOURSE_SSO_SECRET.encode(
            'utf-8'), ssoParams.encode('utf-8'), sha256).hexdigest()

        if not hmac.compare_digest(str(ssoSignature), str(paramSignature)):
            raise AuthException('Could not verify discourse login')

        decodedParams = base64.b64decode(ssoParams)
        kwargs.update({'sso': '', 'sig': '', 'backend': self, 'response':
                       urllib.parse.parse_qsl(decodedParams)})

        return self.strategy.authenticate(*args, **kwargs)
