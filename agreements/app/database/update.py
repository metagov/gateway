import tweepy
import json
from tinydb import TinyDB
from app.auth import auth
from .parser import Parser
from .metadata import Metadata
import pdb

def run():
    api = auth.API()

    db = TinyDB('app/database/db.json', indent=4)
    db.drop_tables() # clears database

    meta = Metadata(db)
    parser = Parser(db, api)

    # iterates through all new mentions
    for status in tweepy.Cursor(
        api.mentions_timeline, 
        tweet_mode="extended", # needed to get full text for longer tweets
        since_id=meta.retrieve('last_status_parsed'), # won't iterate through tweets already in database
        count=200
    ).items():

        parser.parse(status)

        # updates last status id -> next mentions timeline won't see already parsed tweets
        if status.id > meta.retrieve('last_status_parsed'):
            meta.update('last_status_parsed', status.id)
