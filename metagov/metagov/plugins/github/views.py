import json
import logging

from metagov.core.models import ProcessStatus
from metagov.plugins.github.models import Github, GithubIssueReactVote, GithubIssueCommentVote

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