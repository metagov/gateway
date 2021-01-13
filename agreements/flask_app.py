from flask import Flask, abort
from database import update
import json, time

app = Flask(__name__)
last_accessed = time.time()
waittime = 5

db  = {}


# refreshes db dict object
def update_db():
    global db
    with open('database/db.json', 'r') as f:
        db = json.load(f)

# requests a thread from the database, returns None if doesn't exist
def req_thread(thread_id):
    global db
    if thread_id in db['threads']:
        return db['threads'][thread_id]
    else:
        return None

# retrieves a html doc (just being concise :O)
def get_html(name):
    with open(f'web/{name}.html', 'r') as f:
        return f.read()

@app.route('/')
def run():
    global last_accessed
    # calls database update if waittime has passed since last call
    if (time.time() - last_accessed) > waittime:
        update.run()
        update_db()
        last_accessed = time.time()
    
    return get_html('main')

@app.route('/thread/<thread_id>')
def display_thread(thread_id):
    return get_html('thread')

@app.route('/api/<thread_id>')
def api_request(thread_id):
    thread = req_thread(thread_id)

    if thread:
        print(f'returning thread {thread_id}: {thread}')
        return thread
    else:
        abort(400)


if __name__ == "__main__":
    update.run()
    update_db()
    app.run(port=80, debug=True)