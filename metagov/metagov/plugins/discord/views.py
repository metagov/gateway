# import asyncio
import environ
import json
import logging
import requests

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http.response import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from metagov.core.errors import PluginErrorInternal, PluginAuthError
from metagov.core.plugin_manager import AuthorizationType
from metagov.plugins.discord.models import Discord
from requests.models import PreparedRequest

# from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey


logger = logging.getLogger(__name__)

env = environ.Env()
environ.Env.read_env()

# whether to require the installer to be an admin, and request user scopes for the installing user
# if true, the installer's access token will be passed back after installation
# TODO: let driver choose dynamically, or make this a real config somewhere
REQUIRE_INSTALLER_TO_BE_ADMIN = True


class NonAdminInstallError(PluginAuthError):
    default_code = "discord_installer_is_not_admin"
    default_detail = "Non-admin user is not permitted to install"


class AlreadyInstalledError(PluginAuthError):
    default_code = "discord_already_installed"
    default_detail = "This community already has Discord enabled, but for a different guild. Only one Discord guild is permitted per community."


class WrongCommunityError(PluginAuthError):
    default_code = "discord_wrong_community"
    default_detail = "Already installed to this Discord guild for a different community. Uninstall and try again."


def get_authorize_url(state: str, type: str, community=None):
    try:
        client_id = env("DISCORD_CLIENT_ID")
    except ImproperlyConfigured:
        raise PluginAuthError(detail="Client ID not configured")

    scopes_and_permissions = ""
    if type == AuthorizationType.APP_INSTALL:
        scopes_and_permissions = "scope=bot%20identify%20guilds&permissions=8589934591"
    elif type == AuthorizationType.USER_LOGIN:
        scopes_and_permissions = "scope=identify"

    return f"https://discordapp.com/api/oauth2/authorize?response_type=code&client_id={client_id}&state={state}&{scopes_and_permissions}"


def _exchange_code(code):
    data = {
        "client_id": env("DISCORD_CLIENT_ID"),
        "client_secret": env("DISCORD_CLIENT_SECRET"),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": f"{settings.SERVER_URL}/auth/discord/callback",
    }
    resp = requests.post("https://discordapp.com/api/oauth2/token", data=data)
    if not resp.ok:
        logger.error(f"Discord auth failed: {resp.status_code} {resp.reason}")
        raise PluginAuthError

    return resp.json()


def auth_callback(type: str, code: str, redirect_uri: str, community, state=None, request=None, *args, **kwargs):
    """
    OAuth2 callback endpoint handler for authorization code grant type.
    This function does two things:
        1) completes the authorization flow,
        2) enables the Discord plugin for the specified community


    type : AuthorizationType.APP_INSTALL or AuthorizationType.USER_LOGIN
    code : authorization code from the server (Discord)
    redirect_uri : redirect uri from the Driver to redirect to on completion
    community : the Community to enable Discord for
    state : optional state to pass along to the redirect_uri
    """
    logger.debug(f"> auth_callback for guild_id: {request.GET.get('guild_id')}")

    response = _exchange_code(code)
    logger.info(f"---- {response} ----")
    user_access_token = response["access_token"]
    user_refresh_token = response["refresh_token"]

    guild_id = response["guild"]["id"]

    # Get user info
    resp = requests.get(
        "https://www.discordapp.com/api/users/@me",
        headers={"Authorization": f"Bearer {user_access_token}"},
    )
    if not resp.ok:
        logger.error(f"Discord req failed: {resp.status_code} {resp.reason}")
        raise PluginAuthError(detail="Error getting user info for installing user")
    current_user = resp.json()
    logger.debug(current_user)

    if type == AuthorizationType.APP_INSTALL:
        # Check if there are any existing Discord Plugin instances for this Discord team
        # TODO: pull some of this logic into core. Each plugin has its own version of "team_id" that may need to be unique.
        existing_plugin_to_reinstall = None
        for inst in Discord.objects.all():
            if inst.config["guild_id"] == guild_id:
                if inst.community == community:
                    # team matches, community matches

                    # There is already a Discord Plugin enabled for this Community, so we want to delete and recreate it.
                    # This is to support re-installation, which you might want to do if scopes have changed for example.
                    existing_plugin_to_reinstall = inst
                else:
                    # team matches, community doesnt

                    # There is already a Discord Plugin for this guild enabled for a DIFFERENT community, so we error.
                    # Discord admin would need to go into the Discord guild and uninstall the app, if they want to create a Discord Plugin for
                    # the same guild under a different community.
                    logger.error(f"Discord Plugin for guild {guild_id} already exists for another community: {inst}")
                    raise WrongCommunityError
            elif inst.community == community:
                # community matches, team doesnt
                logger.info(
                    f"Trying to install Discord to community {community} for guild_id {guild_id}, but community already has a Discord Plugin enabled for guild {inst.config['guild_id']}"
                )
                raise AlreadyInstalledError

        # Configuration for the new Discord Plugin to create
        plugin_config = {"guild_id": guild_id, "guild_name": response["guild"]["name"]}

        # if REQUIRE_INSTALLER_TO_BE_ADMIN:
        #     # TODO call auth.revoke if anything fails, to uninstall the bot and delete the bot token

        #     if response["guild"]["owner_id"] != current_user["id"]:
        #         raise NonAdminInstallError

        if existing_plugin_to_reinstall:
            logger.info(
                f"Deleting existing Discord plugin found for requested community {existing_plugin_to_reinstall}"
            )
            existing_plugin_to_reinstall.delete()

        plugin = Discord.objects.create(name="discord", community=community, config=plugin_config)
        logger.debug(f"Created Discord plugin: {plugin}")

        # Add some params to redirect (this is specifically for PolicyKit which requires the installer's admin token)
        params = {
            # Metagov community that has the Discord plugin enabled
            "community": community.slug,
            # Discord User ID for installer
            "user_id": current_user["id"] if REQUIRE_INSTALLER_TO_BE_ADMIN else None,
            # Discord User Token for installer
            "user_token": response["access_token"] if REQUIRE_INSTALLER_TO_BE_ADMIN else None,
            # (Optional) State that was originally passed from Driver, so it can validate it
            "state": state,
            # Guild that the user installed PolicyKit to
            "guild_id": guild_id,
        }
        url = add_query_parameters(redirect_uri, params)
        return HttpResponseRedirect(url)

    elif type == AuthorizationType.USER_LOGIN:

        # Add some params to redirect
        params = {
            # Discord User ID for logged-in user
            "user_id": current_user["id"],
            # Discord User Token for logged-in user
            "user_token": response["access_token"],
            # Guild that the user logged into
            "guild_id": guild_id,
            # (Optional) State that was originally passed from Driver, so it can validate it
            "state": state,
        }
        url = add_query_parameters(redirect_uri, params)
        return HttpResponseRedirect(url)

    return HttpResponseBadRequest()


def add_query_parameters(url, params):
    req = PreparedRequest()
    req.prepare_url(url, params)
    return req.url


def process_event(request):
    """
    Handler for processing interaction events from Discord.
    https://discord.com/developers/docs/interactions/receiving-and-responding
    """

    validate_discord_interaction(request)

    json_data = json.loads(request.body)
    logger.debug(json_data)

    if json_data["type"] == 1:
        # PING response
        return JsonResponse({"type": 1})

    if json_data["type"] in [2, 3]:
        # 2 = APPLICATION_COMMAND
        # 3 = MESSAGE_COMPONENT

        guild_id = json_data["guild_id"]
        for plugin in Discord.objects.all():
            if plugin.config["guild_id"] == guild_id:
                logger.info(f"Passing event to {plugin}")
                plugin.receive_event(request)
    # {
    #     "type": 4,
    #     "data": {
    #         "tts": False,
    #         "content": "Congrats on sending your command!",
    #         "embeds": [],
    #         "allowed_mentions": { "parse": [] }
    #     }
    # }
    return HttpResponse()


def validate_discord_interaction(request):
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Signature-Ed25519")
    if not timestamp or not signature:
        raise PluginErrorInternal("Bad request signature")

    raw_body = request.body.decode("utf-8")
    client_public_key = env("DISCORD_PUBLIC_KEY")

    if not verify_key(raw_body, signature, timestamp, client_public_key):
        raise PluginErrorInternal("Bad request signature")


def verify_key(raw_body, signature, timestamp, client_public_key):
    message = timestamp.encode() + raw_body
    try:
        vk = VerifyKey(bytes.fromhex(client_public_key))
        vk.verify(message, bytes.fromhex(signature))
        return True
    except Exception as ex:
        print(ex)
    return False
