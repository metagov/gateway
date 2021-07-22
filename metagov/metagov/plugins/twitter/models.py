import logging

import environ
import metagov.core.plugin_decorators as Registry
import tweepy
from metagov.core.models import AuthType, Plugin
from metagov.core.errors import PluginErrorInternal

logger = logging.getLogger(__name__)


env = environ.Env()
environ.Env.read_env()


class TwitterSecrets:
    api_key = env("TWITTER_API_KEY", default=None)
    api_secret_key = env("TWITTER_API_SECRET_KEY", default=None)
    access_token = env("TWITTER_ACCESS_TOKEN", default=None)
    access_token_secret = env("TWITTER_ACCESS_TOKEN_SECRET", default=None)


"""
TODO: implement oauth2 support, so that communities can authorize this twitter
app to act on behalf of a different account associated with their community.
For now, it only acts on behalf of the same account for all communities.
"""


@Registry.plugin
class Twitter(Plugin):
    name = "twitter"
    auth_type = AuthType.API_KEY
    config_schema = {
        "type": "object",
        "properties": {"allow_posting_tweets": {"type": "boolean"}},
        "required": [],
    }

    class Meta:
        proxy = True

    def tweepy_api(self):
        if getattr(self, "api", None):
            return self.api
        auth = tweepy.OAuthHandler(TwitterSecrets.api_key, TwitterSecrets.api_secret_key)
        auth.set_access_token(TwitterSecrets.access_token, TwitterSecrets.access_token_secret)
        self.api = tweepy.API(auth)
        return self.api

    def initialize(self):
        logger.info(f"Initialized Twitter plugin with config: {self.config}")
        # Do auth during initialization so that it fails fast if any secrets are missing
        self.tweepy_api()

    @Registry.action(
        slug="send-tweet",
        description="Send a tweet",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    )
    def send_tweet(self, parameters):
        if not self.config.get("allow_posting_tweets", False):
            raise PluginErrorInternal

        res = self.tweepy_api().update_status(parameters["text"])
        logger.debug(res)
        return res
