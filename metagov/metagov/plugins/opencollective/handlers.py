import logging
import requests
from django.conf import settings

import metagov.plugins.opencollective.queries as Queries
from django.http.response import HttpResponseBadRequest, HttpResponseRedirect
from metagov.core.errors import PluginAuthError, PluginErrorInternal
from metagov.core.plugin_manager import AuthorizationType
from metagov.core.models import ProcessStatus
from metagov.plugins.opencollective.models import OpenCollective, OPEN_COLLECTIVE_URL, OPEN_COLLECTIVE_GRAPHQL
from requests.models import PreparedRequest
from metagov.core.handlers import PluginRequestHandler




logger = logging.getLogger(__name__)

open_collective_settings = settings.METAGOV_SETTINGS["OPENCOLLECTIVE"]
OC_CLIENT_ID = open_collective_settings["CLIENT_ID"]
OC_CLIENT_SECRET = open_collective_settings["CLIENT_SECRET"]
BOT_ACCOUNT_NAME_SUBSTRING = "governance bot"

class NonBotAccountError(PluginAuthError):
    default_code = "non_bot_account"
    default_detail = f"The Open Collective account name must contains string '{BOT_ACCOUNT_NAME_SUBSTRING}' (case insensitive)."


class NotOneCollectiveError(PluginAuthError):
    default_code = "not_one_collective"
    default_detail = f"The Open Collective account must be a member of exactly 1 collective or organization."

class InsufficientPermissions(PluginAuthError):
    default_code = "insufficient_permissions"
    default_detail = f"The Open Collective account does not have sufficient permissions. Account must be an admin on the collective."

class OpenCollectiveRequestHandler(PluginRequestHandler):
    def construct_oauth_authorize_url(self, type: str, community=None):
        if not OC_CLIENT_ID:
            raise PluginAuthError(detail="Client ID not configured")
        if not OC_CLIENT_SECRET:
            raise PluginAuthError(detail="Client secret not configured")

        admin_scopes = ['email', 'account', 'expenses', 'conversations', 'webhooks']
        # if type == AuthorizationType.APP_INSTALL:    
        # elif type == AuthorizationType.USER_LOGIN:

        return f"{OPEN_COLLECTIVE_URL}/oauth/authorize?response_type=code&client_id={OC_CLIENT_ID}&scope={','.join(admin_scopes)}"

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

        # Get user info
        resp = requests.post(
            OPEN_COLLECTIVE_GRAPHQL,
            json={"query": Queries.me},
            headers={"Authorization": f"Bearer {user_access_token}"}
        )
        logger.debug(resp.request.headers)
        if not resp.ok:
            logger.error(f"OC req failed: {resp.status_code} {resp.reason}")
            raise PluginAuthError(detail="Error getting user info for installing user")
        response = resp.json()
        logger.info(response)
        account_name = response['data']['me']['name'] or ''
        member_of = response['data']['me']['memberOf']
        if not BOT_ACCOUNT_NAME_SUBSTRING in account_name.lower():
            logger.error(f"OC bad account name: {account_name}")
            raise NonBotAccountError

        if not member_of or member_of['totalCount'] != 1:
            raise NotOneCollectiveError

        collective = member_of['nodes'][0]['account']['slug']
        logger.info('collective: ')
        logger.info(collective)


        if type == AuthorizationType.APP_INSTALL:
            plugin_config = {"collective_slug": collective, "access_token": user_access_token}
            plugin = OpenCollective.objects.create(
                name="opencollective", community=community, config=plugin_config, community_platform_id=collective
            )
            logger.debug(f"Created OC plugin: {plugin}")
            try:
                plugin.initialize()
            except PluginErrorInternal as e:
                plugin.delete()
                if 'permission' in e.detail:
                    raise InsufficientPermissions
                else:
                    raise PluginAuthError

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
            # TODO Implement
            # Validate that is member of collective

            # Add some params to redirect
            params = { "state": state }
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
    resp = requests.post(f"{OPEN_COLLECTIVE_URL}/oauth/token", data=data)
    if not resp.ok:
        logger.error(f"OC auth failed: {resp.status_code} {resp.reason}")
        raise PluginAuthError

    return resp.json()


def add_query_parameters(url, params):
    req = PreparedRequest()
    req.prepare_url(url, params)
    return req.url

