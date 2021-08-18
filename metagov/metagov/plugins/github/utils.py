""" Authentication """

import jwt, datetime, environ, logging, requests

from metagov.core.errors import PluginErrorInternal

import sys

TEST = 'test' in sys.argv

logger = logging.getLogger(__name__)
env = environ.Env()
environ.Env.read_env()


def get_private_key():
    with open(env("PATH_TO_GITHUB_PRIVATE_KEY")) as f:
        lines = f.readlines()
    if len(lines) == 1:
        return lines[0]
    else:
        return "".join(lines)


def get_jwt():
    if TEST: return ""

    payload = {
        # GitHub App's identifier
        "iss": env("GITHUB_APP_ID"),
        # issued at time, 60 seconds in the past to allow for clock drift
        "iat": int(datetime.datetime.now().timestamp()) - 60,
        # JWT expiration time (10 minute maximum)
        "exp": int(datetime.datetime.now().timestamp()) + (9 * 60)
    }
    return jwt.encode(payload, get_private_key(), algorithm="RS256")


def get_access_token(installation_id):
    """Get installation access token using installation id"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {get_jwt()}"
    }
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    resp = requests.request("POST", url, headers=headers)

    if not resp.ok:
        logger.error(f"Error refreshing token: status {resp.status_code}, details: {resp.text}")
        raise PluginErrorInternal(resp.text)
    if resp.content:
        token = resp.json()["token"]
        return token


""" Text generation """


def create_issue_text(vote_type, parameters):

    question = parameters.pop("question")
    help_text = parameters.pop("help_text", None)
    help_text = f"Additional guidance: {help_text}\n\n" if help_text else ""
    max_votes = parameters.pop("max_votes", None)
    max_votes = f" This vote will end when there are {max_votes} total votes." if max_votes else ""

    title = f"VOTE: {question}"

    if vote_type == "react":

        body = (
            "This is a react vote issue. Please vote on the question below, using "
            "thumbs up for yes and thumbs down for no. Other reactions will not be counted."
            f"{max_votes}"
            "\n\n"
            f"{help_text}"
            f"QUESTION: {question}"
        )

    elif vote_type == "comment":

        body = (
            "This is a comment vote issue. Please vote on the question below by leaving a comment with "
            "the text `^^^^<yourvotehere>^^^^`. You can add any additional commentary you like. \n\n"
            "Please note that your vote will not be case sensitive, but spelling _does_ matter. If you try "
            "to vote multiple times, only your first vote will be counted. You may edit your vote as long as "
            "the vote is still open."
            f"{max_votes}"
            "\n\n"
            f"{help_text}"
            f"QUESTION: {question}"
        )

    return title, body


def close_react_vote_text(result, upvotes, downvotes):
    return (
        f"This vote is now closed. The result was {result} with {upvotes} votes for "
        f"and {downvotes} votes against. You may continue commenting and reacting, but it will "
        "have no impact on the result."
    )


def close_comment_vote_text(voter_list, votes):
    outcome = ""
    for name, count in votes.most_common():
        outcome += f"{name}: {count}\n"
    return(
        f"This vote is now closed. You may continue commenting, but it will not affect the result.\n\n"
        f"The result was:\n\n{outcome}\n"
        f"People voting: {', '.join(voter_list)}"
    )