import tweepy
import json
from tinydb import TinyDB, where
from tinydb.database import Document
import auth
import database
import pdb

api = auth.API()

db = TinyDB('agreements/db.json', indent=4)

# active tables for storing tweets and parsed agreement threads
threads = db.table('threads')

meta = database.Metadata(db)
tweets = database.Digester(db)

# iterates through all new mentions
for status in tweepy.Cursor(
    api.mentions_timeline, 
    tweet_mode="extended", # needed to get full text for longer tweets
    since_id=meta.retrieve('last_status_parsed') # won't iterate through tweets already in database
).items():

    tweets.add(status)

    # updates last status id -> next mentions timeline won't see already parsed tweets
    if status.id > meta.retrieve('last_status_parsed'):
        meta.update('last_status_parsed', status.id)

# an agreement might look like this?
'''
agreement
├─sign
├─sign
├─amendment
│ ├─sign
│ ├─sign
│ ├─sign
│ └─passes
└─amendment
  └─amendment
'''