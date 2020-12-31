import tweepy
import json
from tinydb import TinyDB, where
from tinydb.database import Document
import auth
import db_operations

api = auth.API()

db = TinyDB('agreements/db.json', indent=4)

tweets = db.table('tweets')

m = db_operations.Metadata(db)

# iterates through all new mentions
for status in tweepy.Cursor(
    api.mentions_timeline, 
    tweet_mode="extended", 
    since_id=m.retrieve('last_status_parsed')
).items():

    # to be stored in tinydb
    tweet = {
        'type': 'other',    # 
        'parent': -1,       # id of tweet replying to (or -1 if root)
        'text': '',         # tweet text
        'created': '',      # date/time created
        'signed': False,    # 
        'user_id': 0,       # twitter id
        'user_name': ''     # twitter username
    }

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
        
        else:
            tweet['parent'] = status.in_reply_to_status_id
            
        if "+amendment" in status.full_text:
            tweet['type'] = 'amendment'
        
        if "+sign" in status.full_text:
            tweet['signed'] = True

        # saves tweet data into tinydb with tweet id
        tweets.insert(Document(tweet, doc_id=status.id))

    # updates last status parsed if tweet id is larger
    # next time the mentions timeline starts, it won't even see already parsed tweets
    if status.id > m.retrieve('last_status_parsed'):
        m.update('last_status_parsed', status.id)

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