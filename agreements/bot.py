import tweepy
import json
from tinydb import TinyDB
import auth, database
from database.parser import Parser
from database.metadata import Metadata
import pdb

api = auth.API()

db = TinyDB('agreements/db.json', indent=4)
db.drop_tables()
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
..└─amendment
'''