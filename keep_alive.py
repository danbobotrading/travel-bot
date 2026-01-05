import requests
import threading
import time
import os

def keep_choreo_awake():
    """Ping Choreo service to prevent scaling to zero"""
    service_url = os.environ.get('CHOREO_SERVICE_URL', '')
    if not service_url:
        return
    
    while True:
        try:
            # Ping every 4 minutes
            time.sleep(240)
            response = requests.get(f"{service_url}/health", timeout=5)
            if response.status_code == 200:
                print("✅ Pinged Choreo to stay awake")
        except:
            print("⚠️ Keep-alive ping failed")
            time.sleep(60)

# Start in main()
# threading.Thread(target=keep_choreo_awake, daemon=True).start()
