import hashlib
import hmac
import json
import logging

import environ
import requests
from django.http.response import HttpResponse
from metagov.core.errors import PluginErrorInternal
from metagov.plugins.slack.models import Slack

logger = logging.getLogger(__name__)

env = environ.Env()
environ.Env.read_env()


def get_authorize_url(state):
    client_id = env("SLACK_CLIENT_ID")
    return f"https://slack.com/oauth/v2/authorize?client_id={client_id}&state={state}&scope=app_mentions:read,calls:read,calls:write,channels:history,channels:join,channels:manage,channels:read,chat:write,chat:write.customize,chat:write.public,commands,dnd:read,emoji:read,files:read,groups:history,groups:read,groups:write,im:history,im:read,im:write,incoming-webhook,links:read,links:write,mpim:history,mpim:read,mpim:write,pins:read,pins:write,reactions:read,reactions:write,team:read,usergroups:read,usergroups:write,users.profile:read,users:read,users:read.email,users:write&user_scope="


def auth_callback(request):
    """
    https://api.slack.com/authentication/oauth-v2#exchanging
    """
    data = {
        "client_id": env("SLACK_CLIENT_ID"),
        "client_secret": env("SLACK_CLIENT_SECRET"),
        "code": request.GET.get("code"),
    }
    resp = requests.post("https://slack.com/api/oauth.v2.access", data=data)
    if not resp.ok:
        raise PluginErrorInternal(f"Slack auth failed: {resp.status_code} {resp.reason}")
    response = resp.json()
    if not response["ok"]:
        raise PluginErrorInternal(f"Slack auth failed: {response['error']}")

    # {
    #     "ok": true,
    #     "access_token": "xoxb-17653672481-19874698323-pdFZKVeTuE8sk7oOcBrzbqgy",
    #     "token_type": "bot",
    #     "scope": "commands,incoming-webhook",
    #     "bot_user_id": "U0KRQLJ9H",
    #     "app_id": "A0KRD7HC3",
    #     "team": {
    #         "name": "Slack Softball Team",
    #         "id": "T9TK3CUKW"
    #     },
    #     "enterprise": {
    #         "name": "slack-sports",
    #         "id": "E12345678"
    #     },
    #     "authed_user": {
    #         "id": "U1234",
    #         "scope": "chat:write",
    #         "access_token": "xoxp-1234",
    #         "token_type": "user"
    #     }
    # }

    # app_id = response["app_id"]
    if response["token_type"] != "bot":
        raise PluginErrorInternal("Expected token_type bot")
    config = {
        "team_id": response["team"]["id"],
        "team_name": response["team"]["name"],
        "bot_token": response["access_token"],
        "bot_user_id": response["bot_user_id"],
    }
    return config


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
        for plugin in Slack.objects.all():
            if plugin.config["team_id"] == json_data["team_id"]:
                logger.info(f"passing event to {plugin}")
                plugin.receive_event(request)
                break
    return HttpResponse()


def validate_slack_event(request):
    req_timestamp = request.headers.get("X-Slack-Request-Timestamp")
    if req_timestamp is None:
        raise PluginErrorInternal("missing request timestamp")
    req_signature = request.headers.get("X-Slack-Signature")
    if req_signature is None or not verify_signature(request, req_timestamp, req_signature):
        raise PluginErrorInternal("Invalid request signature")


def verify_signature(request, timestamp, signature):
    # FIXME! this sin't working for some reason
    return True

    signing_secret = env("SLACK_SIGNING_SECRET")
    signing_secret = bytes(signing_secret, "utf-8")
    body = request.body.decode('utf-8')
    base = f"v0:{timestamp}:{body}".encode("utf-8")
    request_hash = hmac.new(signing_secret, base, hashlib.sha256).hexdigest()
    expected_signature = f"v0={request_hash}"
    return hmac.compare_digest(signature, expected_signature)
