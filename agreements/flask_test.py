from flask import Flask
import bot
import json
app = Flask(__name__)

@app.route('/')
def run():
    bot.run()
    with open('agreements/db.json', 'r') as f:
        db = json.load(f)
    return db

app.run()