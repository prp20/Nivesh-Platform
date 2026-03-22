import pandas as pd
import requests
import json
from datetime import datetime
from tqdm import tqdm
import os

BASE_URL = "http://localhost:8000/api/v1"
DATA_FILE = "data/new_equity_only.csv"

def migrate_funds():
    if not os.path.exists(DATA_FILE):
        print(f"File not found: {DATA_FILE}")
        return

    df = pd.read_csv(DATA_FILE)
    print(f"Found {len(df)} funds in CSV. Starting migration...")

    for _, row in tqdm(df.iterrows(), total=len(df)):
        # Handle date format DD-MM-YYYY to YYYY-MM-DD
        try:
            inc_date = datetime.strptime(str(row['inception_date']), "%d-%m-%Y").strftime("%Y-%m-%d")
        except:
            inc_date = "2013-01-01" # Fallback

        payload = {
            "scheme_code": str(int(row['scheme_code'])),
            "scheme_name": str(row['scheme_name']),
            "amc_name": str(row['amc_name']),
            "inception_date": inc_date,
            "plan_type": str(row['plan_type']),
            "scheme_category": str(row['scheme_category']),
            "scheme_subcategory": str(row.get('scheme_subcategory', 'Other')),
            "benchmark_index_code": str(row.get('benchmark_index_code', 'NIFTY_50')),
            "is_active": True
        }

        try:
            resp = requests.post(f"{BASE_URL}/funds/", json=payload)
            if resp.status_code not in [200, 201]:
                if "already exists" not in resp.text:
                    print(f"Error for {row['scheme_name']}: {resp.text}")
        except Exception as e:
            print(f"Connection failed for {row['scheme_name']}: {e}")

def migrate_nav_histories():
    # We'll trigger the sync for a few representative funds to keep it fast
    df = pd.read_csv(DATA_FILE)
    top_funds = df.head(10) # Just sync top 10 for demonstration
    
    print(f"Syncing NAV histories for top {len(top_funds)} funds...")
    for _, row in tqdm(top_funds.iterrows(), total=len(top_funds)):
        code = str(int(row['scheme_code']))
        try:
            # Our backend has a sync endpoint
            resp = requests.post(f"{BASE_URL}/sync/fund/{code}")
            if resp.status_code != 200:
                print(f"Sync failed for {code}: {resp.text}")
        except Exception as e:
            print(f"Sync connection error for {code}: {e}")

if __name__ == "__main__":
    print("--- Starting Nivesh Data Migration ---")
    migrate_funds()
    migrate_nav_histories()
    print("--- Migration Task Completed ---")
