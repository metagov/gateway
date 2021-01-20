from flask import Flask, abort
from app.database import update
import json, time

app = Flask(__name__)
last_accessed = time.time()
waittime = 5

db  = {}

# refreshes db dict object
def update_db():
    global db
    with open('app/database/db.json', 'r') as f:
        db = json.load(f)

# requests a thread from the database, returns None if doesn't exist
def req_thread(thread_id):
    global db
    if thread_id in db['threads']:
        return db['threads'][thread_id]
    else:
        return None

def req_status(status_id):
    global db

    status_id = str(status_id)

    statuses = []
    # begins depth first traversal if status id is valid
    if status_id in db['tweets']:
        stack = [status_id]
        # iterates through status tree 
        while stack:
            curr = db['tweets'][str(stack.pop())]
            statuses.append(curr['text'])
            stack.extend(curr['child_ids'])

    return statuses

# retrieves a html doc (just being concise :O)
def get_html(name):
    with open(f'app/web/{name}.html', 'r') as f:
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

# displays a thread
@app.route('/thread/<thread_id>')
def display_thread(thread_id):
    return get_html('thread')

# returns a thread obj through api call
@app.route('/api/t/<thread_id>')
def api_thread_request(thread_id):
    thread = req_thread(thread_id)

    if thread:
        print(f'Returning thread {thread_id}: {thread}')
        return thread
    else:
        abort(400)

@app.route('/api/s/<status_id>')
def api_status_request(status_id):
    status_list = req_status(status_id)

    if status_list:
        print(f'Returning status list {status_id}: {status_list}')
        return {
            "data": status_list
        }
    else:
        abort(400)
    

update.run()
update_db()

