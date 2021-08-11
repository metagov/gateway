import json
import logging
import requests
import environ

from metagov.core.models import ProcessStatus
from metagov.core.plugin_constants import AuthorizationType
from metagov.plugins.github.models import Github, GithubIssueReactVote, GithubIssueCommentVote
from metagov.plugins.github.utils import get_jwt

logger = logging.getLogger(__name__)

env = environ.Env()
environ.Env.read_env()

GITHUB_APP_NAME = env("GITHUB_APP_NAME")

def process_event(request):

    json_data = json.loads(request.body)

    if "X-GitHub-Event" in request.headers:

        for plugin in Github.objects.all():

            if int(plugin.config["installation_id"]) == int(json_data["installation"]["id"]):

                logger.info(f"Passing event to {plugin}")
                plugin.github_webhook_receiver(request)

                for process_type in [GithubIssueCommentVote, GithubIssueReactVote]:
                    for process in process_type.objects.filter(plugin=plugin, status=ProcessStatus.PENDING.value):
                        if hasattr(process, "receive_webhook"):
                            process.receive_webhook(request)


def get_authorize_url(state, type, community):
    if type == AuthorizationType.APP_INSTALL:
        return f"https://github.com/apps/{GITHUB_APP_NAME}/installations/new/?state={state}"


def auth_callback(type, code, redirect_uri, community, state, request):

    # check if plugin already created for this community and delete it if it exists
    existing_plugin = Github.objects.filter(community=community)
    for instance in existing_plugin:  # should only be one instance
        logger.info(f"Deleting existing Github plugin found for requested community {existing_plugin}")

    # get owner info given installation_id
    installation_id = request.GET.get("installation_id")
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {get_jwt()}"
    }
    url = f"https://api.github.com/app/installations/{installation_id}"
    resp = requests.request("GET", url, headers=headers)
    owner = resp.json()["account"]["login"]

    # create new plugin
    plugin_config = {"owner": owner, "installation_id": installation_id}
    plugin = Github.objects.create(name="github", community=community, config=plugin_config)
    logger.info(f"Created Github plugin {plugin}")
