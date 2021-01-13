import tweepy
import json
from tinydb import TinyDB
from auth import auth
from .parser import Parser
from .metadata import Metadata
import pdb

def run():
    api = auth.API()

    db = TinyDB('database/db.json', indent=4)
    # db.drop_tables() # clears database
    meta = Metadata(db)
    parser = Parser(db)

    # iterates through all new mentions
    for status in tweepy.Cursor(
        api.mentions_timeline, 
        tweet_mode="extended", # needed to get full text for longer tweets
        since_id=meta.retrieve('last_status_parsed'), # won't iterate through tweets already in database
        count=20
    ).items():

        parser.add(status)

        # updates last status id -> next mentions timeline won't see already parsed tweets
        if status.id > meta.retrieve('last_status_parsed'):
            meta.update('last_status_parsed', status.id)


    parser.parse_all()

if __name__ == "__main__":
    run()