import json
import logging
import requests
import environ

from metagov.core.models import ProcessStatus
from metagov.core.plugin_manager import AuthorizationType
from metagov.plugins.github.models import Github, GithubIssueReactVote, GithubIssueCommentVote
from metagov.plugins.github.utils import get_jwt
from metagov.core.handlers import PluginRequestHandler

logger = logging.getLogger(__name__)

env = environ.Env()
environ.Env.read_env()

GITHUB_APP_NAME = env("GITHUB_APP_NAME")


class GithubRequestHandler(PluginRequestHandler):
    def handle_incoming_webhook(self, request):
        json_data = json.loads(request.body)
        installation = json_data.get("installation")
        if not installation:
            return

        if "X-GitHub-Event" in request.headers:

            for plugin in Github.objects.filter(community_platform_id=str(installation["id"])):
                logger.info(f"Passing event to {plugin}")
                plugin.github_webhook_receiver(request)

                for process_type in [GithubIssueCommentVote, GithubIssueReactVote]:
                    for process in process_type.objects.filter(plugin=plugin, status=ProcessStatus.PENDING.value):
                        if hasattr(process, "receive_webhook"):
                            process.receive_webhook(request)

    def construct_oauth_authorize_url(self, type, community):
        if type == AuthorizationType.APP_INSTALL:
            return f"https://github.com/apps/{GITHUB_APP_NAME}/installations/new/"

    def handle_oauth_callback(self, type, code, redirect_uri, community, state, request, *args, **kwargs):

        # check if plugin already created for this community and delete it if it exists
        existing_plugin = Github.objects.filter(community=community)
        for instance in existing_plugin:  # should only be one instance
            logger.info(f"Deleting existing Github plugin found for requested community {instance}")

        # get owner info given installation_id
        installation_id = request.GET.get("installation_id")
        headers = {"Accept": "application/vnd.github.v3+json", "Authorization": f"Bearer {get_jwt()}"}
        url = f"https://api.github.com/app/installations/{installation_id}"
        resp = requests.request("GET", url, headers=headers)
        owner = resp.json()["account"]["login"]

        # create new plugin
        plugin_config = {"owner": owner, "installation_id": installation_id}
        plugin = Github.objects.create(
            name="github", community=community, config=plugin_config, community_platform_id=str(installation_id)
        )
        logger.info(f"Created Github plugin {plugin}")
