from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running on Choreo - Port 8080"

@app.route('/health')
def health():
    return "OK", 200

def run():
    # CHOREO REQUIRES PORT 8080
    port = 8080  # Fixed port for Choreo
    print(f"🌐 Health endpoint: http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
