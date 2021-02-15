import json
import tweepy
from tinydb import TinyDB
from app.auth import auth

# api and database references are needed in many other modules
api = auth.API()
db = TinyDB('app/database/db.json', indent=4)

def retrieve(convert_to, tag):
    return convert_to(db.table('metadata').get(doc_id=1)[tag])

class Consts:
    like_value = retrieve(int, 'like_value')
    like_limit = retrieve(int, 'like_limit')
    retweet_value = retrieve(int, 'retweet_value')
    retweet_limit = retrieve(int, 'retweet_limit')
    tax_rate = retrieve(float, 'tax_rate')