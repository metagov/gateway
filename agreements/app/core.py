import json
import tweepy
from tinydb import TinyDB
from app.auth import auth

# api and database references are needed in many other modules
api = auth.API()
db = TinyDB('app/database/db.json', indent=4)
