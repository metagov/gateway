import logging

from metagov.core.plugin_manager import AuthorizationType, Registry, Parameters, VotingStandard
import tweepy
from metagov.core.models import AuthType, Plugin
from metagov.core.errors import PluginErrorInternal
from metagov.core.utils import get_configuration

logger = logging.getLogger(__name__)




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

        api_key = get_configuration("TWITTER_API_KEY", community=self.community)
        api_secret_key = get_configuration("TWITTER_API_SECRET_KEY", community=self.community)
        access_token = get_configuration("TWITTER_ACCESS_TOKEN", community=self.community)
        access_token_secret = get_configuration("TWITTER_ACCESS_TOKEN_SECRET", community=self.community)

        auth = tweepy.OAuthHandler(api_key, api_secret_key)
        auth.set_access_token(access_token, access_token_secret)
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
    def send_tweet(self, text):
        if not self.config.get("allow_posting_tweets", False):
            raise PluginErrorInternal

        res = self.tweepy_api().update_status(text)
        return res._json

    @Registry.action(
        slug="send-dm",
        description="Send a direct message",
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "text": {"type": "string"}
            },
            "required": ["user_id", "text"]
        }
    )
    def send_direct_message(self, user_id, text):
        user_id = int(user_id)
        res = self.tweepy_api().send_direct_message(user_id, text)
        return res._json

    @Registry.action(
        slug="get-user-id",
        description="Gets user id of a Twitter user",
        input_schema={
            "type": "object",
            "properties": {"screen_name": {"type": "string"}},
            "required": ["screen_name"]
        }
    )
    def get_user_id(self, screen_name):
        try:
            user = self.tweepy_api().get_user(screen_name)
            return user.id

        except tweepy.error.TweepError as e:
            if e.api_code == 50:
                return False

    @Registry.event_producer_task()
    def my_task_function(self):
        api = self.tweepy_api()
        since_id = self.state.get("since_id")

        # the first time we start up, just fetch the latest to get the since_id, so we dont send a firehose of events
        count = 200 if since_id else 1

        cursor = tweepy.Cursor(api.user_timeline, since_id=since_id, count=count)
        found_new_tweets = False
        for tweet in cursor.items():
            found_new_tweets = True
            # logger.debug(tweet._json)
            user = tweet._json.pop("user")
            data = tweet._json
            initiator = {"user_id": user["id"], "provider": "twitter"}
            self.send_event_to_driver(event_type="timeline_tweet", initiator=initiator, data=data)

            if not since_id or tweet.id > since_id:
                since_id = tweet.id

        if found_new_tweets:
            logger.debug(f"Retrieved new tweets, updating since_id to {since_id}")
            self.state.set("since_id", since_id)
