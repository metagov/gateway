import tweepy
import json
from tinydb import TinyDB, Query
from tinydb.database import Document
from tinydb.operations import *
import auth

api = auth.API()
db = TinyDB('agreements/db.json')

class Metadata:
    def __init__(self, db):
        self.db = db

        # initializes metadata entry in database if it hasn't been created yet
        if not self.db.contains(doc_id=0):
            self.db.insert(Document(
                {
                    'last_status_parsed': 1
                }, 
                doc_id=0))

    # retrieves metadata dict from tinydb
    def get_data(self):
        return self.db.get(doc_id=0)

    def get_last_status_parsed(self):
        return self.get_data()['last_status_parsed']

    def set_last_status_parsed(self, id):
        self.db.update(
            set('last_status_parsed', id),
            doc_ids=[0]
        )

m = Metadata(db)

# iterates through all new mentions
for status in tweepy.Cursor(
    api.mentions_timeline, 
    tweet_mode="extended", 
    since_id=m.get_last_status_parsed()
).items():

    # to be stored in tinydb
    tweet = {
        'type': 'other',
        'text': '',
        'created': '',
        'signed': False,
        'user_id': 0,
        'user_name': ''
    }

    print(status.id)

    # ensures tweet not already in database
    # (should be redundant now that it only checks new tweets)
    if not db.contains(doc_id=status.id):
        tweet['text'] = status.full_text
        tweet['user_id'] = status.user.id
        tweet['user_name'] = status.user.screen_name
        tweet['created'] = str(status.created_at)

        # checks if tweet is a root (not a reply)
        if not status.in_reply_to_status_id:
            # agreement proposal
            if "+agreement" in status.full_text:
                tweet['type'] = 'agreement'
            
        if "+amendment" in status.full_text:
            tweet['type'] = 'amendment'
        
        if "+sign" in status.full_text:
            tweet['signed'] = True

        # saves tweet data into tinydb with tweet id
        db.insert(Document(tweet, doc_id=status.id))
    else:
        print('you got me@!')

    # updates last status parsed if tweet id is larger
    # next time the mentions timeline starts, it won't even see already parsed tweets
    if status.id > m.get_last_status_parsed(): 
        m.set_last_status_parsed(status.id)

# resaves database json to an indented version for easier reading
with open('agreements/db.json', 'r') as f: data = json.load(f)
with open('agreements/human.json', 'w') as f: json.dump(data, f, indent=4)


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