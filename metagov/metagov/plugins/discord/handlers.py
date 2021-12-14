import json
import logging
import requests
from django.conf import settings

from django.http.response import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from metagov.core.errors import PluginErrorInternal, PluginAuthError
from metagov.core.plugin_manager import AuthorizationType
from metagov.core.models import ProcessStatus
from metagov.plugins.discord.models import Discord, DiscordVote
from requests.models import PreparedRequest
from metagov.core.handlers import PluginRequestHandler

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError


logger = logging.getLogger(__name__)

discord_settings = settings.METAGOV_SETTINGS["DISCORD"]
DISCORD_CLIENT_ID = discord_settings["CLIENT_ID"]
DISCORD_CLIENT_SECRET = discord_settings["CLIENT_SECRET"]
DISCORD_PUBLIC_KEY = discord_settings["PUBLIC_KEY"]

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


class PluginNotInstalledError(PluginAuthError):
    default_code = "discord_plugin_not_installed"
    default_detail = "Discord plugin has not been installed to any guilds that this user belongs to."


class DiscordRequestHandler(PluginRequestHandler):
    def handle_incoming_webhook(self, request):
        """
        Handler for processing interaction events from Discord.
        https://discord.com/developers/docs/interactions/receiving-and-responding


        The request body is an Interaction object: https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-object
        """
        json_data = json.loads(request.body)
        logger.debug(f"received discord request: {json_data}")

        validate_discord_interaction(request)

        if json_data["application_id"] != DISCORD_CLIENT_ID:
            raise PluginErrorInternal("Received event with wrong application ID")

        if json_data["type"] == 1:
            # PING response
            return JsonResponse({"type": 1})

        community_platform_id = str(json_data.get("guild_id"))

        # Process type 2, APPLICATION_COMMAND (a user sending a slash command)
        if json_data["type"] == 2:
            # Pass the interaction event to the Plugin for the Guild it occured in
            for plugin in Discord.objects.filter(community_platform_id=community_platform_id):
                logger.info(f"Passing interaction request to {plugin}")
                response_data = plugin.receive_event(request)
                if response_data:
                    return JsonResponse(response_data)

        # Process type 3, MESSAGE_COMPONENT (a user interacting with an interactive message component that was posted by the bot. for example, clicking a voting button.)
        if json_data["type"] == 3:
            # Pass the interaction event to all active governance processes in this guild
            # TODO: maybe should pass message components to Plugins too, in case bots are posting interactive messages
            active_processes = DiscordVote.objects.filter(
                plugin__community_platform_id=community_platform_id, status=ProcessStatus.PENDING.value
            )
            for process in active_processes:
                logger.info(f"Passing interaction request to {process}")
                response_data = process.receive_webhook(request)
                if response_data:
                    return JsonResponse(response_data)

        return HttpResponse()

    def construct_oauth_authorize_url(self, type: str, community=None):
        if not DISCORD_CLIENT_ID:
            raise PluginAuthError(detail="Client ID not configured")

        scopes_and_permissions = ""
        if type == AuthorizationType.APP_INSTALL:
            scopes_and_permissions = "scope=applications.commands%20bot%20identify%20guilds&permissions=8589934591"
        elif type == AuthorizationType.USER_LOGIN:
            scopes_and_permissions = "scope=identify"

        return f"https://discordapp.com/api/oauth2/authorize?response_type=code&client_id={DISCORD_CLIENT_ID}&{scopes_and_permissions}"

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

        # Get user info
        resp = requests.get(
            "https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {user_access_token}"}
        )
        logger.debug(resp.request.headers)
        if not resp.ok:
            logger.error(f"Discord req failed: {resp.status_code} {resp.reason}")
            raise PluginAuthError(detail="Error getting user info for installing user")
        current_user = resp.json()

        # TODO: create MetagovId
        # current_user_id = current_user["id"]
        # current_user_username = current_user["username"]

        if type == AuthorizationType.APP_INSTALL:
            guild_id = response["guild"]["id"]
            # Check if there are any existing Discord Plugin instances for this Discord team
            # TODO: pull some of this logic into core. Each plugin has its own version of "team_id" that may need to be unique.
            community_platform_id = str(guild_id)
            existing_plugin_to_reinstall = Discord.objects.filter(community_platform_id=community_platform_id).first()
            if existing_plugin_to_reinstall:
                if existing_plugin_to_reinstall.community != community:
                    # There is already a Discord Plugin for this guild enabled for a DIFFERENT community, so we error.
                    # Discord admin would need to go into the Discord guild and uninstall the app, if they want to create a Discord Plugin for
                    # the same guild under a different community.
                    logger.error(
                        f"Discord Plugin for guild {guild_id} already exists for another community: {existing_plugin_to_reinstall}"
                    )
                    raise WrongCommunityError

            already_installed_plugins = Discord.objects.filter(community=community).exclude(
                community_platform_id=community_platform_id
            )
            if already_installed_plugins.exists():
                # community matches, team doesnt
                logger.info(
                    f"Trying to install Discord to community {community} for guild_id {guild_id}, but community already has a Discord Plugin enabled for guild {inst.config['guild_id']}"
                )
                raise AlreadyInstalledError

            # Configuration for the new Discord Plugin to create
            plugin_config = {"guild_id": guild_id, "guild_name": response["guild"]["name"]}

            if REQUIRE_INSTALLER_TO_BE_ADMIN:
                # TODO call auth.revoke if anything fails, to uninstall the bot and delete the bot token

                if response["guild"]["owner_id"] != current_user["id"]:
                    raise NonAdminInstallError

            if existing_plugin_to_reinstall:
                logger.info(
                    f"Deleting existing Discord plugin found for requested community {existing_plugin_to_reinstall}"
                )
                existing_plugin_to_reinstall.delete()

            plugin = Discord.objects.create(
                name="discord", community=community, config=plugin_config, community_platform_id=community_platform_id
            )
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

            # Find which guilds this user is a part of
            resp = requests.get(
                "https://discord.com/api/users/@me/guilds",
                headers={"Authorization": f"Bearer {response['access_token']}"},
            )
            user_guilds = resp.json()
            logger.debug(user_guilds)

            # Build a list of guild IDs that this user belongs do that are integrated with Metagov
            integrated_guilds = []
            for guild in user_guilds:
                for inst in Discord.objects.all():
                    if str(inst.config["guild_id"]) == str(guild["id"]):
                        guild_id_name = f"{guild['id']}:{guild['name']}"
                        logger.debug(f">>>keeping {guild_id_name}")
                        integrated_guilds.append(guild_id_name)

            if not integrated_guilds:
                raise PluginNotInstalledError

            # Add some params to redirect
            params = {
                # Discord User ID for logged-in user
                "user_id": current_user["id"],
                # Discord User Token for logged-in user
                "user_token": response["access_token"],
                # Metagov-integrated guilds that this user belongs to
                "guild[]": integrated_guilds,
                # (Optional) State that was originally passed from Driver, so it can validate it
                "state": state,
            }
            url = add_query_parameters(redirect_uri, params)
            return HttpResponseRedirect(url)

        return HttpResponseBadRequest()


def _exchange_code(code):
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": f"{settings.SERVER_URL}/auth/discord/callback",
    }
    resp = requests.post("https://discordapp.com/api/oauth2/token", data=data)
    if not resp.ok:
        logger.error(f"Discord auth failed: {resp.status_code} {resp.reason}")
        raise PluginAuthError

    return resp.json()


def add_query_parameters(url, params):
    req = PreparedRequest()
    req.prepare_url(url, params)
    return req.url


def validate_discord_interaction(request):
    timestamp = request.headers.get("X-Signature-Timestamp")
    signature = request.headers.get("X-Signature-Ed25519")
    if not timestamp or not signature:
        raise PluginErrorInternal("Bad request signature: missing headers")

    raw_body = request.body.decode("utf-8")
    client_public_key = DISCORD_PUBLIC_KEY

    if not verify_key(raw_body, signature, timestamp, client_public_key):
        raise PluginErrorInternal("Bad request signature: verification failed")


def verify_key(raw_body, signature, timestamp, client_public_key):
    vf_key = VerifyKey(bytes.fromhex(client_public_key))
    try:
        vf_key.verify(f"{timestamp}{raw_body}".encode(), bytes.fromhex(signature))
    except BadSignatureError:
        return False
    return True
