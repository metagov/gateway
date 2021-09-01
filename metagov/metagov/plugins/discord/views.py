import environ
import json
import logging
import requests

from django.core.exceptions import ImproperlyConfigured
from django.http.response import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from metagov.core.errors import PluginErrorInternal, PluginAuthError
from metagov.core.plugin_manager import AuthorizationType
from metagov.plugins.discord.models import Discord
from requests.models import PreparedRequest

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

    if type == AuthorizationType.APP_INSTALL:
        team = None
        if community:
            try:
                plugin = Discord.objects.get(community=community)
                team = plugin.config.get("guild_id")
                logger.debug(
                    f"Discord is already enabled for {community}, so only allowing re-installation to the same team ({team})"
                )
            except Discord.DoesNotExist:
                pass

        return f"https://discordapp.com/api/oauth2/authorize?client_id={client_id}&state={state}&team={team or ''}&permissions=8589934591&scope=bot%20identify%20guilds"
    if type == AuthorizationType.USER_LOGIN:
        return f"https://discordapp.com/api/oauth2/authorize?client_id={client_id}&state={state}&scope=identify%20guilds"


def auth_callback(type: str, code: str, redirect_uri: str, community, state=None):
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
    data = {
        "client_id": env("DISCORD_CLIENT_ID"),
        "client_secret": env("DISCORD_CLIENT_SECRET"),
        "grant_type": "authorization_code",
        "code": code
    }
    resp = requests.post("https://discordapp.com/api/oauth2/token", data=data)
    if not resp.ok:
        logger.error(f"Discord auth failed: {resp.status_code} {resp.reason}")
        raise PluginAuthError

    response = resp.json()
    if not response["ok"]:
        raise PluginAuthError(code=response["error"])

    logger.info(f"---- {response} ----")

    team_id = response["guild"]["id"]

    # Get user info
    req = urllib.request.Request('https://www.discordapp.com/api/users/@me')
    req.add_header('Authorization', 'Bearer %s' % response["access_token"])
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req)
    current_user = json.loads(resp.read().decode('utf-8'))

    if type == AuthorizationType.APP_INSTALL:
        if response["token_type"] != "Bearer":
            raise PluginAuthError(detail="Incorrect token_type")

        # Check if there are any existing Discord Plugin instances for this Discord team
        # TODO: pull some of this logic into core. Each plugin has its own version of "team_id" that may need to be unique.
        existing_plugin_to_reinstall = None
        for inst in Discord.objects.all():
            if inst.config["team_id"] == team_id:
                if inst.community == community:
                    # team matches, community matches

                    # There is already a Discord Plugin enabled for this Community, so we want to delete and recreate it.
                    # This is to support re-installation, which you might want to do if scopes have changed for example.
                    existing_plugin_to_reinstall = inst
                else:
                    # team matches, community doesnt

                    # There is already a Discord Plugin for this team enabled for a DIFFERENT community, so we error.
                    # Discord admin would need to go into the Discord guild and uninstall the app, if they want to create a Discord Plugin for
                    # the same guild under a different community.
                    logger.error(f"Discord Plugin for team {team_id} already exists for another community: {inst}")
                    raise WrongCommunityError
            elif inst.community == community:
                # community matches, team doesnt
                logger.info(
                    f"Trying to install Discord to community {community} for team_id {team_id}, but community already has a Discord Plugin enabled for team {inst.config['team_id']}"
                )
                raise AlreadyInstalledError

        # Configuration for the new Discord Plugin to create
        plugin_config = {
            "team_id": team_id,
            "team_name": response["guild"]["name"]
        }

        if REQUIRE_INSTALLER_TO_BE_ADMIN:
            # TODO call auth.revoke if anything fails, to uninstall the bot and delete the bot token

            if response["guild"]["owner_id"] != current_user["id"]:
                raise NonAdminInstallError

        if existing_plugin_to_reinstall:
            logger.info(f"Deleting existing Discord plugin found for requested community {existing_plugin_to_reinstall}")
            existing_plugin_to_reinstall.delete()
        plugin = Discord.objects.create(name="discord", community=community, config=plugin_config)
        logger.info(f"Created Discord plugin {plugin}")

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
        }
        url = add_query_parameters(redirect_uri, params)
        return HttpResponseRedirect(url)

    elif type == AuthorizationType.USER_LOGIN:
        if response["token_type"] != "Bearer":
            raise PluginAuthError(detail="Unexpected token_type")

        # Add some params to redirect
        params = {
            # Discord User ID for logged-in user
            "user_id": current_user["id"],
            # Discord User Token for logged-in user
            "user_token": response["access_token"],
            # Team that the user logged into
            "team_id": team_id,
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
