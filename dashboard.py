from flask import Flask, render_template
from flask_socketio import SocketIO
import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

logs = []

@app.route("/")
def index():
    return render_template("index.html", logs=logs)

def push_log(data):
    logs.append(data)
    socketio.emit("new_log", data)

def run_dashboard():
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
