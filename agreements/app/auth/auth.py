import tweepy
import json

def API():
    # loading API keys from json
    with open('app/auth/apikeys.json', 'r') as f:
        keys = json.load(f)

    # sending keys to authenticator
    auth = tweepy.OAuthHandler(
        keys['API key'], 
        keys['API key secret'])

    auth.set_access_token(
        keys['Access token'], 
        keys['Acess token secret'])

    return tweepy.API(auth)