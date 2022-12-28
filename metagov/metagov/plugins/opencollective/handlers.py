import json
import logging
import requests
from django.conf import settings

from django.http.response import HttpResponseBadRequest, HttpResponseRedirect
from metagov.core.errors import PluginAuthError
from metagov.core.plugin_manager import AuthorizationType
from metagov.core.models import ProcessStatus
from metagov.metagov.plugins.opencollective.models import OPEN_COLLECTIVE_GRAPHQL
from metagov.plugins.opencollective.models import OpenCollective
from requests.models import PreparedRequest
from metagov.core.handlers import PluginRequestHandler




logger = logging.getLogger(__name__)

open_collective_settings = settings.METAGOV_SETTINGS["OPEN_COLLECTIVE"]
OC_CLIENT_ID = open_collective_settings["CLIENT_ID"]
OC_CLIENT_SECRET = open_collective_settings["CLIENT_SECRET"]

class OpenCollectiveRequestHandler(PluginRequestHandler):
    def construct_oauth_authorize_url(self, type: str, community=None):
        if not OC_CLIENT_ID:
            raise PluginAuthError(detail="Client ID not configured")
        if not OC_CLIENT_SECRET:
            raise PluginAuthError(detail="Client secret not configured")

        admin_scopes = ['email', 'account', 'expenses', 'conversations', 'webhooks']
        # if type == AuthorizationType.APP_INSTALL:    
        # elif type == AuthorizationType.USER_LOGIN:

        return f"https://opencollective.com/oauth/authorizeauthorize?response_type=code&client_id={OC_CLIENT_ID}&scope={admin_scopes.join(',')}"

    def handle_oauth_callback(
        self,
        type: str,
        code: str,
        redirect_uri: str,
        community,
        request,
        state=None,
        external_id=None,
        *args,
        **kwargs,
    ):
        """
        OAuth2 callback endpoint handler for authorization code grant type.
        This function does two things:
            1) completes the authorization flow,
            2) enables the OC plugin for the specified community


        type : AuthorizationType.APP_INSTALL or AuthorizationType.USER_LOGIN
        code : authorization code from the server (OC)
        redirect_uri : redirect uri from the Driver to redirect to on completion
        community : the Community to enable OC for
        state : optional state to pass along to the redirect_uri
        """
        logger.debug(f"> auth_callback for oc")

        response = _exchange_code(code)
        logger.info(f"---- {response} ----")
        user_access_token = response["access_token"]

        logger.info(OPEN_COLLECTIVE_GRAPHQL)
        # Get user info
        resp = requests.post(
            OPEN_COLLECTIVE_GRAPHQL,
            json={"query": "{ me { id name email } }"},
            headers={"Authorization": f"Bearer {user_access_token}"}
        )
        logger.debug(resp.request.headers)
        if not resp.ok:
            logger.error(f"OC req failed: {resp.status_code} {resp.reason}")
            raise PluginAuthError(detail="Error getting user info for installing user")
        current_user = resp.json()
        logger.debug(current_user)

        # TODO: prompt choose collective?
        collective = 'metagov-test-collective-2'

        if type == AuthorizationType.APP_INSTALL:
            plugin_config = {"collective_slug": collective, "api_key": user_access_token}
            plugin = OpenCollective.objects.create(
                name="opencollective", community=community, config=plugin_config, community_platform_id=collective
            )
            logger.debug(f"Created OC plugin: {plugin}")

            params = {
                # Metagov community that has the OC plugin enabled
                "community": community.slug,
                # (Optional) State that was originally passed from Driver, so it can validate it
                "state": state,
                # Collective that the user installed PolicyKit to
                "collective": collective,
            }
            url = add_query_parameters(redirect_uri, params)
            return HttpResponseRedirect(url)

        elif type == AuthorizationType.USER_LOGIN:
            # Add some params to redirect
            params = {
                # # Discord User ID for logged-in user
                # "user_id": current_user["id"],
                # # Discord User Token for logged-in user
                # "user_token": response["access_token"],
                # # Metagov-integrated guilds that this user belongs to
                # "guild[]": integrated_guilds,
                # # (Optional) State that was originally passed from Driver, so it can validate it
                "state": state,
            }
            url = add_query_parameters(redirect_uri, params)
            return HttpResponseRedirect(url)

        return HttpResponseBadRequest()


def _exchange_code(code):
    data = {
        "client_id": OC_CLIENT_ID,
        "client_secret": OC_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": f"{settings.SERVER_URL}/auth/opencollective/callback",
    }
    resp = requests.post("https://opencollective.com/oauth/token", data=data)
    if not resp.ok:
        logger.error(f"OC auth failed: {resp.status_code} {resp.reason}")
        raise PluginAuthError

    return resp.json()


def add_query_parameters(url, params):
    req = PreparedRequest()
    req.prepare_url(url, params)
    return req.url

