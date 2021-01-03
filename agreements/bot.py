import tweepy
import json
from tinydb import TinyDB
import auth, database
import pdb

api = auth.API()

db = TinyDB('agreements/db.json', indent=4)
db.drop_tables()
meta = database.Metadata(db)
parser = database.Parser(db)

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

# for status in db.table('tweets'):
#     print(status.doc_id)
#     parser.parse(status)

for thingy in sorted(list(db.table('tweets')._read_table().keys())):
    parser.parse(db.table('tweets').get(doc_id=thingy))

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