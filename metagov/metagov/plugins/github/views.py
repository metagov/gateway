import json
import logging

from metagov.core.models import ProcessStatus
from metagov.core.plugin_constants import AuthType
from metagov.plugins.github.models import Github, GithubIssueReactVote, GithubIssueCommentVote
from metagov.plugins.github.utils import get_access_token

logger = logging.getLogger(__name__)


def process_event(request):

    json_data = json.loads(request.body)

    if "X-GitHub-Event" in request.headers:

        for plugin in Github.objects.all():

            if plugin.config["installation_id"] == json_data["installation"]:

                logger.info(f"Passing event to {plugin}")
                plugin.receive_event(request)

                # FIXME: programatically iterate through governance processes?
                for process_type in [GithubIssueCommentVote, GithubIssueReactVote]:
                    for process in process_type.objects.filter(plugin=plugin, status=ProcessStatus.PENDING.value):
                        process.receive_event(request)

    return HttpResponse()


def get_authorize_url(state, type):

    if type == AuthType.APP_INSTALL:

        return f"https://github.com/apps/metagovapp/installations/new/?state={state}"


def auth_callback(type, code, redirect_uri, community, state=None):

    # get access token given ID
    token = get_access_token(code)  # NOTE: where does 'code' come from? is it installation_id?

    # check if plugin already created for this community and delete it if it exists
    existing_plugin = Github.objects.filter(community=community)
    for instance in existing_plugin:  # should only be one instance
        logger.info(f"Deleting existing Github plugin found for requested community {existing_plugin}")

    # create new plugin
    plugin_config = {
        "owner": ?,  #  owner should be passed to us by Github but I don't know where that data ended up
        "installation_id": code  # ???
    }
    plugin = Github.objects.create(name="github", community=community, config=plugin_config)
    logger.info(f"Created Github plugin {plugin}")

    return HttpResponseRedirect(redirect_uri)
