import json
import tweepy
from tinydb import TinyDB
from app.auth import auth

api = auth.API()
db = TinyDB('app/database/db.json', indent=4)