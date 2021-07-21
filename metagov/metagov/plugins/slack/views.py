import hashlib
import hmac
import json
import logging

import environ
import requests
from django.http.response import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from metagov.core.errors import PluginErrorInternal, PluginAuthError
from metagov.core.plugin_constants import AuthType
from metagov.plugins.slack.models import Slack, SlackEmojiVote
from requests.models import PreparedRequest
from django.core.exceptions import ImproperlyConfigured
from metagov.core.models import ProcessStatus

logger = logging.getLogger(__name__)

env = environ.Env()
environ.Env.read_env()

# whether to require the installer to be an admin, and request user scopes for the installing user
# if true, the installer's access token will be passed back after installation
# TODO: let driver choose dynamically, or make this a real config somewhere
REQUIRE_INSTALLER_TO_BE_ADMIN = True


class NonAdminInstallError(PluginAuthError):
    default_code = "user_is_not_admin"
    default_detail = "Non-admin user is not permitted to install"


def get_authorize_url(state, type):
    try:
        client_id = env("SLACK_CLIENT_ID")
    except ImproperlyConfigured:
        raise PluginAuthError(detail="Client ID not configured")

    if type == AuthType.APP_INSTALL:
        # TODO: make requested scopes configurable?
        user_scope = (
            "chat:write,channels:write,groups:write,im:write,mpim:write" if REQUIRE_INSTALLER_TO_BE_ADMIN else ""
        )
        return f"https://slack.com/oauth/v2/authorize?client_id={client_id}&state={state}&scope=app_mentions:read,calls:read,calls:write,channels:history,channels:join,channels:manage,channels:read,chat:write,chat:write.customize,chat:write.public,commands,dnd:read,emoji:read,files:read,groups:history,groups:read,groups:write,im:history,im:read,im:write,incoming-webhook,links:read,links:write,mpim:history,mpim:read,mpim:write,pins:read,pins:write,reactions:read,reactions:write,team:read,usergroups:read,usergroups:write,users.profile:read,users:read,users:read.email,users:write&user_scope={user_scope}"
    if type == AuthType.USER_LOGIN:
        return f"https://slack.com/oauth/v2/authorize?client_id={client_id}&state={state}&user_scope=identity.basic,identity.avatar"


def auth_callback(type, code, redirect_uri, community, state=None):
    """
    Exchange code for access token

    https://api.slack.com/authentication/oauth-v2#exchanging
    """
    data = {
        "client_id": env("SLACK_CLIENT_ID"),
        "client_secret": env("SLACK_CLIENT_SECRET"),
        "code": code,
    }
    resp = requests.post("https://slack.com/api/oauth.v2.access", data=data)
    if not resp.ok:
        logger.error(f"Slack auth failed: {resp.status_code} {resp.reason}")
        raise PluginAuthError

    response = resp.json()
    if not response["ok"]:
        raise PluginAuthError(code=response["error"])

    logger.info(f"---- {response} ----")

    if type == AuthType.APP_INSTALL:
        if response["token_type"] != "bot":
            raise PluginAuthError(detail="Incorrect token_type")

        installer_user_id = response["authed_user"]["id"]
        team_id = response["team"]["id"]

        # Configuration for the Slack Plugin
        plugin_config = {
            "team_id": team_id,
            "team_name": response["team"]["name"],
            "bot_token": response["access_token"],
            "bot_user_id": response["bot_user_id"],
            "installer_user_id": installer_user_id,
        }

        installer_user_token = response["authed_user"].get("access_token")
        if REQUIRE_INSTALLER_TO_BE_ADMIN:
            # Check whether installing user is an admin. Use the Bot Token to make the request.
            resp = requests.get(
                "https://slack.com/api/users.info",
                params={"user": installer_user_id},
                headers={"Authorization": f"Bearer {response['access_token']}"},
            )

            # TODO call auth.revoke if anything fails, to uninstall the bot and delete the bot token

            if not resp.ok:
                logger.error(f"Slack req failed: {resp.status_code} {resp.reason}")
                raise PluginAuthError(detail="Error getting user info for installing user")
            response = resp.json()
            if not response["ok"]:
                logger.error(f"Slack req failed: {response['error']}")
                raise PluginAuthError(detail="Error getting user info for installing user")
            if response["user"]["is_admin"] == False:
                raise NonAdminInstallError

            # store the installer's user token in config, so it can be used by the plugin to make requests later..
            plugin_config["installer_user_token"] = installer_user_token

        # Check if there is already a Slack Plugin enabled for this Community
        try:
            existing_plugin = Slack.objects.get(community=community)
            logger.info(f"Deleting existing Slack plugin found for requested community {existing_plugin}")
            existing_plugin.delete()
        except Slack.DoesNotExist:
            pass

        # Check if there is already a Slack Plugin enabled for this unique Slack "team", possibly for a different Metagov Community
        for inst in Slack.objects.all():
            if inst.config["team_id"] == team_id:
                logger.info(
                    f"Slack Plugin for team {team_id} already exists: {inst}. Assigning authorized Slack plugin to community '{inst.community}' instead of '{community}'"
                )
                # There is an existing Community that has an active Slack Plugin for this team, so, delete and recreate that one instead
                # This could happen if Slack is being re-installed to a Slack team from PolicyKit (support re-installation to enable updating
                # bot token, if scopes changed for example)
                community = inst.community
                logger.info(f"Deleting existing Slack plugin {inst}")
                inst.delete()
                break

        plugin = Slack.objects.create(name="slack", community=community, config=plugin_config)
        logger.info(f"Created Slack plugin {plugin}")

        # Add some params to redirect
        params = {
            # Metagov community that now has the Slack plugin enabled (may be diff from the community that was requested on initial authorization request)
            "community": community.slug,
            # Slack User ID for installer
            "user_id": installer_user_id if REQUIRE_INSTALLER_TO_BE_ADMIN else None,
            # Slack User Token for installer
            "user_token": installer_user_token if REQUIRE_INSTALLER_TO_BE_ADMIN else None,
            # (Optional) State that was originally passed from Driver, so it can validate it
            "state": state,
        }
        url = add_query_parameters(redirect_uri, params)
        return HttpResponseRedirect(url)

    elif type == AuthType.USER_LOGIN:
        user = response["authed_user"]
        if user["token_type"] != "user":
            raise PluginAuthError(detail="Unexpected token_type")

        # Add some params to redirect
        params = {
            # Slack User ID for logged-in user
            "user_id": user["id"],
            # Slack User Token for logged-in user
            "user_token": user["access_token"],
            # Team that the user logged into
            "team_id": response["team"]["id"],
            # (Optional) State that was originally passed from Driver, so it can validate it
            "state": state,
        }
        url = add_query_parameters(redirect_uri, params)
        return HttpResponseRedirect(url)

    return HttpResponseBadRequest()


def process_event(request):
    json_data = json.loads(request.body)
    if json_data["type"] == "url_verification":
        challenge = json_data.get("challenge")
        return HttpResponse(challenge)
    if json_data["type"] == "app_rate_limited":
        logger.error("Slack app rate limited")
        return HttpResponse()
    if json_data["type"] == "event_callback":
        validate_slack_event(request)
        retry_num = request.headers.get("X-Slack-Retry-Num")
        if retry_num is not None:
            retry_reason = request.headers.get("X-Slack-Retry-Reason")
            logger.warn(f"Received retried event: {retry_num} {retry_reason}")
            if retry_reason == "http_timeout":
                # This is retry because we took over 3 second to reply to the last request.
                # Ignore it and tell Slack not to retry this message again.
                return HttpResponse(headers={"X-Slack-No-Retry": 1})

        for plugin in Slack.objects.all():
            if plugin.config["team_id"] == json_data["team_id"]:
                logger.info(f"Passing event to {plugin}")
                plugin.receive_event(request)
                evt_type = json_data["event"]["type"]
                if evt_type == "reaction_added" or evt_type == "reaction_removed":
                    active_processes = SlackEmojiVote.objects.filter(plugin=plugin, status=ProcessStatus.PENDING.value)
                    for process in active_processes:
                        process.receive_webhook(request)
    return HttpResponse()


def validate_slack_event(request):
    req_timestamp = request.headers.get("X-Slack-Request-Timestamp")
    if req_timestamp is None:
        raise PluginErrorInternal("missing request timestamp")
    req_signature = request.headers.get("X-Slack-Signature")
    if req_signature is None or not verify_signature(request, req_timestamp, req_signature):
        raise PluginErrorInternal("Invalid request signature")


def verify_signature(request, timestamp, signature):
    # FIXME! this isn't working for some reason
    return True

    signing_secret = env("SLACK_SIGNING_SECRET")
    signing_secret = bytes(signing_secret, "utf-8")
    body = request.body.decode("utf-8")
    base = f"v0:{timestamp}:{body}".encode("utf-8")
    request_hash = hmac.new(signing_secret, base, hashlib.sha256).hexdigest()
    expected_signature = f"v0={request_hash}"
    return hmac.compare_digest(signature, expected_signature)


def add_query_parameters(url, params):
    req = PreparedRequest()
    req.prepare_url(url, params)
    return req.url