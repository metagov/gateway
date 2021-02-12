import tweepy
from app import core
from .parser import Parser
from .metadata import Metadata

def run():
    core.db.drop_tables() # clears database

    meta = Metadata(core.db)
    parser = Parser(core.db, core.api)

    # iterates through all new mentions
    for status in tweepy.Cursor(
        core.api.mentions_timeline, 
        tweet_mode="extended", # needed to get full text for longer tweets
        since_id=meta.retrieve('last_status_parsed'), # won't iterate through tweets already in database
        count=200
    ).items():

        parser.parse(status)

        # updates last status id -> next mentions timeline won't see already parsed tweets
        if status.id > meta.retrieve('last_status_parsed'):
            meta.update('last_status_parsed', status.id)
