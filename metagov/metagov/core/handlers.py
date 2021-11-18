import base64
import importlib
import inspect
import json
import logging
from typing import Optional

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseRedirect
from django.http.response import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from metagov.core import utils
from metagov.core.app import MetagovApp
from metagov.core.errors import PluginAuthError
from metagov.core.models import Community, ProcessStatus
from metagov.core.plugin_manager import AuthorizationType, plugin_registry
from requests.models import PreparedRequest

logger = logging.getLogger(__name__)

import importlib


class PluginRequestHandler:
    def construct_oauth_authorize_url(self, type: str, community=None) -> str:
        raise NotImplementedError

    def handle_oauth_callback(
        self, type: str, code: str, redirect_uri: str, community, state=None, external_id=None, *args, **kwargs
    ) -> HttpResponse:
        raise NotImplementedError

    def handle_incoming_webhook(self, request) -> Optional[HttpResponse]:
        raise NotImplementedError


class MetagovRequestHandler:
    def __init__(self, app: MetagovApp):
        self.app = app

    def handle_incoming_webhook(
        self, request, plugin_name, community_slug=None, community_platform_id=None
    ) -> HttpResponse:
        logger.debug(f"Received webhook request: {plugin_name} ({community_platform_id or 'no community_platform_id'}) ({community_slug or 'no community'})")

        if community_slug:
            # Pass request a specific plugin instance
            community = self.app.get_community(community_slug)
            plugin = community.get_plugin(plugin_name, community_platform_id)
            response = None
            if plugin._webhook_receiver_function:
                webhook_handler_fn = getattr(plugin, plugin._webhook_receiver_function)
                logger.debug(f"Passing webhook request to: {plugin}")
                try:
                    response = webhook_handler_fn(request)
                except Exception as e:
                    logger.error(f"Plugin '{plugin}' failed to process webhook: {e}")

            # Pass request to all pending GovernanceProcesses for this plugin, too
            for cls in plugin._process_registry.values():
                processes = cls.objects.filter(plugin=plugin, status=ProcessStatus.PENDING.value)
                if processes.count():
                    logger.debug(f"{processes.count()} pending processes for plugin instance '{plugin}'")
                for process in processes:
                    try:
                        process.receive_webhook(request)
                    except Exception as e:
                        logger.error(f"Process '{process}' failed to process webhook: {e}")

            return response or HttpResponse()

        # Pass request to platform-wide handlers (e.g. Slack, where there is one webhook for all communities)
        plugin_handler = self._get_plugin_request_handler(plugin_name)
        if not plugin_handler:
            logger.error(f"No request handler found for '{plugin_name}'")
            return HttpResponseNotFound()
        try:
            return plugin_handler.handle_incoming_webhook(request) or HttpResponse()
        except NotImplementedError:
            logger.error(f"Webhook handler not implemented for '{plugin_name}'")
            return HttpResponseNotFound()

    def handle_oauth_authorize(
        self,
        request,
        plugin_name,
        redirect_uri=None,
        type=None,
        community_slug=None,
        metagov_id=None,
    ) -> HttpResponse:
        """
        Oauth2 authorize for installation and/or user login

        :param request: Django request object
        :param plugin_name: name of plugin to install or to use for user authentication
        :param type: auth type (user login or app installation)
        :param redirect_uri: where to redirect after auth flow is done
        :param community_slug: community to install to (optional for installation, ignored for user login)
        :param metagov_id: metagov_id of logged in user, if exists
        """
        if not plugin_registry.get(plugin_name):
            return HttpResponseBadRequest(f"No such plugin: {plugin_name}")
        # auth type (user login or app installation)
        type = type or request.GET.get("type", AuthorizationType.APP_INSTALL)
        # community to install to (optional for installation, ignored for user login)
        community_slug = community_slug or request.GET.get("community")
        # where to redirect after auth flow is done
        redirect_uri = redirect_uri or request.GET.get("redirect_uri")
        # metagov_id of logged in user, if exists
        metagov_id = metagov_id or request.GET.get("metagov_id")
        # state to pass along to final redirect after auth flow is done
        received_state = request.GET.get("state")
        request.session["received_authorize_state"] = received_state
        if type != AuthorizationType.APP_INSTALL and type != AuthorizationType.USER_LOGIN:
            return HttpResponseBadRequest(
                f"Parameter 'type' must be '{AuthorizationType.APP_INSTALL}' or '{AuthorizationType.USER_LOGIN}'"
            )

        logger.debug(f"Handling {type} authorization request for {plugin_name} to community '{community_slug or 'new community'}'")

        plugin_handler = self._get_plugin_request_handler(plugin_name)
        if not plugin_handler:
            logger.error(f"No request handler found for '{plugin_name}'")
            return HttpResponseNotFound()

        community = None
        if type == AuthorizationType.APP_INSTALL:
            if community_slug:
                try:
                    community = Community.objects.get(slug=community_slug)
                except Community.DoesNotExist:
                    return HttpResponseBadRequest(f"No such community: {community_slug}")
            else:
                community = Community.objects.create()
                # TODO: delete the community if installation fails.
                logger.debug(f"Created new community for installing {plugin_name}: {community}")
            community_slug = str(community.slug)

        # Create the state
        nonce = utils.generate_nonce()
        state = {
            nonce: {"community": community_slug, "redirect_uri": redirect_uri, "type": type, "metagov_id": metagov_id}
        }
        state_str = json.dumps(state).encode("ascii")
        state_encoded = base64.b64encode(state_str).decode("ascii")
        # Store nonce in the session so we can validate the callback request
        request.session["nonce"] = nonce

        url = plugin_handler.construct_oauth_authorize_url(type=type, community=community)
        logger.debug(f"Redirecting to {url}")
        return redirect_with_params(url, state=state_encoded)

    def handle_oauth_callback(self, request, plugin_name) -> HttpResponse:
        """
        Oauth2 callback for installation and/or user login
        """
        logger.debug(f"Plugin auth callback received request: {request.GET}")
        if not plugin_registry.get(plugin_name):
            return HttpResponseBadRequest(f"No such plugin: {plugin_name}")
        state_str = request.GET.get("state")
        if not state_str:
            return HttpResponseBadRequest("missing state")

        # Validate and decode state
        nonce = request.session.get("nonce")
        if not nonce:
            return HttpResponseBadRequest("missing session nonce")

        plugin_handler = self._get_plugin_request_handler(plugin_name)
        if not plugin_handler:
            logger.error(f"No request handler found for '{plugin_name}'")
            return HttpResponseNotFound()

        state = OAuthState(state_str, nonce)
        logger.debug(f"Decoded state: {state.__dict__}")

        if not state.redirect_uri:
            return HttpResponseBadRequest("bad state: redirect_uri is missing")

        # params to include on the redirect
        state_to_pass = request.session.get("received_authorize_state")
        redirect_params = {"state": state_to_pass, "community": state.community}

        if request.GET.get("error"):
            return redirect_with_params(state.redirect_uri, **redirect_params, error=request.GET.get("error"))

        code = request.GET.get("code")
        if not code:
            return redirect_with_params(state.redirect_uri, **redirect_params, error="server_error")

        community = None
        if state.type == AuthorizationType.APP_INSTALL:
            # For installs, validate the community
            if not state.community:
                return redirect_with_params(state.redirect_uri, **redirect_params, error="bad_state")
            try:
                community = Community.objects.get(slug=state.community)
            except Community.DoesNotExist:
                return redirect_with_params(state.redirect_uri, **redirect_params, error="community_not_found")

        try:
            response = plugin_handler.handle_oauth_callback(
                request=request,
                type=state.type,
                code=code,
                redirect_uri=state.redirect_uri,
                community=community,
                state=state_to_pass,
                metagov_id=state.metagov_id,
            )

            return response if response else redirect_with_params(state.redirect_uri, **redirect_params)
        except PluginAuthError as e:
            return redirect_with_params(
                state.redirect_uri, **redirect_params, error=e.get_codes(), error_description=e.detail
            )

    def _get_plugin_request_handler(self, plugin_name) -> Optional[PluginRequestHandler]:
        try:
            module = importlib.import_module(f"metagov.plugins.{plugin_name}.handlers")
        except ModuleNotFoundError:
            return None
        members = inspect.getmembers(
            module, predicate=lambda o: inspect.isclass(o) and issubclass(o, PluginRequestHandler)
        )
        classes = [h for (k, h) in members if k != "PluginRequestHandler"]
        return classes[0]() if classes else None


def redirect_with_params(url, **kwargs):
    req = PreparedRequest()
    req.prepare_url(url, kwargs)
    return HttpResponseRedirect(req.url)


class OAuthState:
    def __init__(self, encoded_state, nonce):
        state_obj = json.loads(base64.b64decode(encoded_state).decode("ascii"))
        state = state_obj.get(nonce)
        if not state:
            raise Exception("nonce not in state")
        for key in state:
            setattr(self, key, state[key])
        for key in ["redirect_uri", "community", "metagov_id", "type"]:
            if not hasattr(self, key):
                setattr(self, key, None)
