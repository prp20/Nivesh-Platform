import asyncio
import requests
import json
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1"

async def recompute_all():
    print(f"[{datetime.now()}] Initializing Global Metrics Recomputation (Rf = 6.5%)...")
    
    try:
        # 1. Fetch all funds
        resp = requests.get(f"{API_BASE}/funds/?limit=500")
        if resp.status_code != 200:
            print(f"Failed to fetch funds: {resp.status_code}")
            return
            
        funds = resp.json().get("items", [])
        print(f"Found {len(funds)} assets for analysis.")
        
        # 2. Trigger compute for each
        for fund in funds:
            code = fund["scheme_code"]
            print(f"Triggering analysis for {code}...")
            trigger_resp = requests.post(f"{API_BASE}/metrics/{code}/compute")
            if trigger_resp.status_code == 200:
                print(f"Successfully queued {code}")
            else:
                print(f"Failed to queue {code}: {trigger_resp.status_code}")
            
            # Rate limiting for background tasks
            await asyncio.sleep(2)
            
    except Exception as e:
        print(f"Error during global recompute: {e}")

if __name__ == "__main__":
    asyncio.run(recompute_all())
