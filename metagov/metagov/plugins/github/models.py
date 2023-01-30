import requests, json, logging
from collections import Counter

from metagov.core.plugin_manager import Registry, Parameters, VotingStandard
from metagov.core.models import Plugin, GovernanceProcess, ProcessStatus, AuthType
from metagov.core.errors import PluginErrorInternal
import metagov.plugins.github.schemas as Schemas
from metagov.plugins.github.utils import (get_access_token, create_issue_text, close_comment_vote_text,
    close_react_vote_text, get_jwt)

logger = logging.getLogger(__name__)


@Registry.plugin
class Github(Plugin):
    name = 'github'
    config_schema = Schemas.github_app_config_schema
    auth_type = AuthType.OAUTH
    community_platform_id_key = "installation_id"

    class Meta:
        proxy = True

    def refresh_token(self):
        """Requests a new installation access token from Github using a JWT signed by private key."""
        installation_id = self.config["installation_id"]
        self.state.set("installation_id", installation_id)
        token = get_access_token(installation_id, community=self.community)
        self.state.set("installation_access_token", token)

    def initialize(self):
        self.state.set("owner", self.config["owner"])
        self.refresh_token()
        logger.info(f"Initialized Slack Plugin for community with installation ID {self.config['installation_id']}")

    def parse_github_webhook(self, request):

        if 'payload' in request.POST:
            body = json.loads(request.POST['payload'])
        else:
            body = json.loads(request.body)

        action_target_type = request.headers["X_GITHUB_EVENT"]
        action_type = body["action"]
        initiator = {"user_id": body["sender"]["id"], "user_name": body["sender"]["login"], "provider": "github"}

        return action_type, action_target_type, initiator, body

    def github_webhook_receiver(self, request):
        action_type, action_target_type, initiator, body = self.parse_github_webhook(request)
        logger.info(f"Received webhook event '{action_type} {action_target_type}' by user {initiator['user_id']}")
        self.send_event_to_driver(event_type=f"{action_type} {action_target_type}", data=body, initiator=initiator)

    def github_request(self, method, route, data=None, add_headers=None, refresh=False, use_jwt=False):
        """Makes request to Github. If status code returned is 401 (bad credentials), refreshes the
        access token and tries again. Refresh parameter is used to make sure we only try once."""

        if use_jwt:
            authorization = f"Bearer {get_jwt(community=self.community)}"
        else:
            authorization =  f"token {self.state.get('installation_access_token')}"

        headers = {
            "Authorization": authorization,
            "Accept": "application/vnd.github.v3+json"
        }
        if add_headers:
            headers.update(add_headers)

        url = f"https://api.github.com{route}"
        logger.info(f"Making request {method} to {route}")
        resp = requests.request(method, url, headers=headers, json=data)

        if resp.status_code == 401 and refresh == False and use_jwt == False:
            logger.info(f"Bad credentials, refreshing token and retrying")
            self.refresh_token()
            return self.github_request(method=method, route=route, data=data, add_headers=add_headers, refresh=True)
        if not resp.ok:
            logger.error(f"Request error for {method}, {route}; status {resp.status_code}, details: {resp.text}")
            raise PluginErrorInternal(resp.text)
        if resp.content:
            return resp.json()
        return None

    @Registry.action(
        slug="method",
        input_schema={
            "type": "object",
            "properties": {"method": {"type": "string"}, "route": {"type": "string"}},
            "required": ["route"],
        },
        description="Perform any Github method (provided sufficient scopes)",
    )
    def method(self, route, method="GET", **kwargs):
        """
        Action to perform any method in https://docs.github.com/en/rest/overview/endpoints-available-for-github-apps

        Example usage:
        curl -iX POST "https://metagov.policykit.org/api/internal/action/github.method" -H  "accept: application/json"
             -H  "X-Metagov-Community: github-tmq3pkxt9" -d '{"parameters":{
                 "method": "GET",
                 "route":"/repos/{owner}/{repo}/issues/comments/{comment_id}",
                 "comment_id": "123123",
                 "repo": "my_repo"}}'
        """
        try:
            interpolated_route = route.format(
                owner=self.state.get("owner"),
                installation_id=self.config["installation_id"],
                **kwargs
            )
        except PluginErrorInternal as e:
            logger.warn(f"Route for method with parameters {kwargs} and state {self.state} not found")
            return
        try:
            return self.github_request(method, interpolated_route, data=kwargs)
        except PluginErrorInternal as e:
            logger.warn(f"Method {interpolated_route} failed with error {e}")

    @Registry.action(
        slug='create-issue',
        description='creates issue in a repository',
        input_schema=Schemas.create_issue_parameters
    )
    def create_issue(self, title, repo_name, body):
        owner = self.state.get("owner")
        data = {"title": title, "body": body}
        return self.github_request(method="post", route=f"/repos/{owner}/{repo_name}/issues", data=data)

    @Registry.action(
        slug='get-installation',
        description='get information about this github installation'
    )
    def get_installation(self):
        return self.github_request(method="get", route=f"/app/installations/{self.config['installation_id']}", use_jwt=True)


"""
GOVERNANCE PROCESSES
"""

@Registry.governance_process
class GithubIssueReactVote(GovernanceProcess):
    name = 'issue-react-vote'
    plugin_name = 'github'
    input_schema = Schemas.issue_react_vote_parameters
    YES = "yes"
    NO = "no"

    class Meta:
        proxy = True

    def start(self, parameters: Parameters):

        # copy owner & repo to state
        self.state.set("owner", self.plugin_inst.config["owner"])
        self.state.set("repo", parameters.repo_name)
        self.state.set("max_votes", parameters.max_votes)

        # create an issue to use as a vote:
        action_params = parameters._json
        action_params["title"], action_params["body"] = create_issue_text("react", action_params)
        issue = self.plugin_inst.create_issue(**action_params)

        self.state.set("issue_number", issue["number"])
        self.state.set("bot_id", issue["user"]["id"])
        self.status = ProcessStatus.PENDING.value
        self.url = f"https://github.com/{self.plugin_inst.config['owner']}/{parameters.repo_name}/issues/{issue['number']}"
        self.outcome = {
            "issue_number": issue["number"],
            "votes": {self.YES: 0, self.NO: 0}
        }
        self.save()
        logger.info(f"Starting IssueReactVote with issue # {issue['number']}")

    def get_basic_info(self):
        return self.state.get("owner"), self.state.get("repo"), self.state.get("issue_number")

    def get_vote_data(self):

        owner, repo, issue_number = self.get_basic_info()

        # Get issue react count
        headers = {"Accept": "application/vnd.github.squirrel-girl-preview"}
        reactions = self.plugin_inst.github_request(
            method="get", route=f"/repos/{owner}/{repo}/issues/{issue_number}/reactions", add_headers=headers)

        upvotes, downvotes = reactions_to_user_lists(reactions)
        upvotes_num, downvotes_num = len(upvotes), len(downvotes)
        if upvotes_num > downvotes_num:
            result = "pass"
        elif downvotes_num > upvotes_num:
            result = "fail"
        else:
            result = "tie"

        vote_count_dict = {
            self.YES: {"users": upvotes, "count": upvotes_num},
            self.NO: {"users": downvotes, "count": downvotes_num}
        }
        return upvotes_num, downvotes_num, result, vote_count_dict

    def close_vote(self, upvotes, downvotes, result):

        # Add a comment to the issue declaring the vote closed and showing the results.
        owner, repo, issue_number = self.get_basic_info()
        close_text = close_react_vote_text(upvotes, downvotes, result)
        self.plugin_inst.github_request(method="post", data={"body": close_text},
            route=f"/repos/{owner}/{repo}/issues/{issue_number}/comments")

        # Close the issue
        self.plugin_inst.github_request(
            method="post", route=f"/repos/{owner}/{repo}/issues/{issue_number}", data={"state": "closed"})

    def close(self):
        upvotes, downvotes, result, vote_count_dict = self.get_vote_data()
        self.close_vote(upvotes, downvotes, result)
        self.outcome["votes"] = vote_count_dict
        self.outcome["result"] = result
        self.status = ProcessStatus.COMPLETED.value
        self.save()
        owner, repo, issue_number = self.get_basic_info()
        logger.info(f"Closing IssueReactVote {owner}/{repo} - issue # {issue_number}")

    def update(self):
        upvotes,downvotes,result,vote_count_dict = self.get_vote_data()
        self.outcome["votes"] = vote_count_dict
        max_votes = self.state.get("max_votes")
        if max_votes and (upvotes + downvotes >= max_votes):
            self.outcome["result"] = result
            self.status = ProcessStatus.COMPLETED.value
            self.close_vote()

        self.save()
        owner, repo, issue_number = self.get_basic_info()
        logger.info(f"Updating IssueReactVote {owner}/{repo} - issue # {issue_number}")

def reactions_to_user_lists(reaction_list):
    """Convert list of reactions from GitHub API into list of usernames for upvote and downvote"""
    upvotes = []
    downvotes = []
    for r in reaction_list:
        if r["content"] not in ["+1", "-1"] or r["user"]["type"] != "User":
            continue

        username = r["user"]["login"]
        if r["content"] == "+1":
            upvotes.append(username)
        elif r["content"] == "-1":
            downvotes.append(username)
    upvotes.sort()
    downvotes.sort()
    return upvotes, downvotes


@Registry.governance_process
class GithubIssueCommentVote(GovernanceProcess):
    name = 'issue-comment-vote'
    plugin_name = 'github'
    input_schema = Schemas.issue_comment_vote_parameters

    class Meta:
        proxy = True

    def start(self, parameters: Parameters):

        # copy owner & repo to state
        self.state.set("owner", self.plugin_inst.config["owner"])
        self.state.set("repo", parameters.repo_name)
        self.state.set("max_votes", parameters.max_votes)

        # create an issue to use as a vote:
        action_params = parameters._json
        action_params["title"], action_params["body"] = create_issue_text("comment", action_params)
        issue = self.plugin_inst.create_issue(**action_params)

        # save
        self.state.set("issue_number", issue["number"])
        self.state.set("bot_id", issue["user"]["id"])
        self.status = ProcessStatus.PENDING.value
        self.save()
        logger.info(f"Starting IssueCommentVote with issue # {issue['number']}")

    def get_basic_info(self):
        return self.state.get("owner"), self.state.get("repo"), self.state.get("issue_number")

    def get_vote_data(self):
        """Gets vote data from issue comments, looking for text between strings _VOTE_ and _ENDVOTE_.
        Only counts the first comment for a given user. Not case sensitive, and removes spaces."""

        owner, repo, issue_number = self.get_basic_info()

        # Get issue comments
        comments = self.plugin_inst.github_request(
            method="get", route=f"/repos/{owner}/{repo}/issues/{issue_number}/comments")

        voter_list = []  #
        votes = Counter()
        for comment in comments:
            body, user, user_id = comment["body"], comment["user"]["login"], comment["user"]["id"]
            if user in voter_list or user_id == self.state.get("bot_id"):
                continue
            voter_list.append(user)
            vote_split = body.split("^^^^")
            if len(vote_split) >= 3:
                vote_text = vote_split[1].lower()
                votes[vote_text] += 1

        return voter_list, votes

    def close_vote(self, voter_list, votes):

        # Add a comment to the issue declaring the vote closed and show the results.
        owner, repo, issue_number = self.get_basic_info()
        close_text = close_comment_vote_text(voter_list, votes)
        self.plugin_inst.github_request(method="post", data={"body": close_text},
             route=f"/repos/{owner}/{repo}/issues/{issue_number}/comments")

        # Close the issue
        self.plugin_inst.github_request(
            method="post", route=f"/repos/{owner}/{repo}/issues/{issue_number}", data={"state": "closed"})

    def close(self, voter_list=None, votes=None):
        if not voter_list or not votes:
            voter_list, votes = self.get_vote_data()
        self.close_vote(voter_list, votes)
        self.status = ProcessStatus.COMPLETED.value
        self.save()
        owner, repo, issue_number = self.get_basic_info()
        logger.info(f"Closing IssueCommentVote {owner}/{repo} - issue # {issue_number}")

    def receive_webhook(self, request):
        action_type, action_target_type, initiator, body = self.plugin_inst.parse_github_webhook(request)
        if action_target_type != "issue_comment" or initiator["user_id"] == self.state.get("bot_id"):
            return
        if body["issue"]["number"] == self.state.get("issue_number") and action_type in ["created", "edited", "deleted"]:
            voter_list, votes = self.get_vote_data()
            if self.state.get("max_votes") and sum(votes.values()) >= self.state.get("max_votes"):
                self.close(voter_list, votes)
