#!/usr/bin/env python3
"""
MINIMAL BOT FOR CHOREO DEPLOYMENT TEST
"""

import os
import logging
from flask import Flask
from threading import Thread

# Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Flask app for Choreo
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot deployment test - SUCCESS"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/ping')
def ping():
    return "pong", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

def main():
    print("=" * 50)
    print("🤖 MINIMAL DEPLOYMENT TEST")
    print("=" * 50)
    
    # Start Flask server
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Keep running
    print("✅ Service started successfully")
    print(f"🌐 Health check: http://0.0.0.0:{os.environ.get('PORT', 8080)}/health")
    print("=" * 50)
    
    # Keep the main thread alive
    import time
    while True:
        time.sleep(3600)  # Sleep for 1 hour

if __name__ == "__main__":
    main()
