from flask import Flask
from flask import render_template
import bot
import json

app = Flask(__name__)

@app.route('/')
def run():
    bot.run()
    with open('db.json', 'r') as f:
        db = f.read()
    return render_template('report.html', report=db)

app.run()