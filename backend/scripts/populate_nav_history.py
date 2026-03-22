import pandas as pd
import requests
import json
from mftool import Mftool
from tqdm import tqdm
from datetime import datetime
import time

# Configuration
API_URL = "http://localhost:8000/api/v1"
INPUT_DATE_FORMAT = "%d-%m-%Y"
OUTPUT_DATE_FORMAT = "%Y-%m-%d"

def get_all_funds():
    """Fetch all funds currently in the database to get their scheme codes."""
    try:
        # Fetching a reasonable limit (current seed is ~283, backend allows up to 500)
        response = requests.get(f"{API_URL}/funds/?skip=0&limit=500")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching funds: {e}")
        return []

def populate_nav_data():
    mf = Mftool()
    funds = get_all_funds()
    
    if not funds:
        print("No funds found in database. Please seed funds first.")
        return

    print(f"Found {len(funds)} funds. Starting NAV data population...")

    success_count = 0
    fail_count = 0

    for fund in tqdm(funds):
        scheme_code = fund['scheme_code']
        scheme_name = fund['scheme_name']

        try:
            # Fetch historical NAV
            # mftool returns history as a dict or dataframe
            history = mf.get_scheme_historical_nav(scheme_code, as_Dataframe=True)
            
            if history is not None and not history.empty:
                history.reset_index(inplace=True)
                # Ensure date is in YYYY-MM-DD for the backend
                history['date'] = pd.to_datetime(history['date'], format=INPUT_DATE_FORMAT)
                history['date_str'] = history['date'].dt.strftime(OUTPUT_DATE_FORMAT)
                history['nav'] = history['nav'].astype(float)
                
                # Format for BulkNavUpload schema: {"date": nav_value}
                nav_dict = {row['date_str']: row['nav'] for _, row in history.iterrows()}
                
                payload = {"data": nav_dict}
                
                # Post to bulk endpoint
                resp = requests.post(
                    f"{API_URL}/navs/{scheme_code}/bulk", 
                    json=payload,
                    timeout=30
                )
                
                if resp.status_code in [200, 201]:
                    success_count += 1
                    # Trigger metrics recomputation immediately for this fund
                    requests.post(f"{API_URL}/metrics/{scheme_code}/compute")
                else:
                    print(f"\nFailed to upload for {scheme_code} ({scheme_name}): {resp.status_code}")
                    fail_count += 1
            else:
                print(f"\nNo history found for {scheme_code} ({scheme_name})")
                fail_count += 1
                
        except Exception as e:
            print(f"\nError processing {scheme_code}: {e}")
            fail_count += 1
            
        # Subtle sleep to prevent overwhelming mftool or local server
        time.sleep(0.1)

    print(f"\nPopulation complete!")
    print(f"Success: {success_count}")
    print(f"Failures: {fail_count}")

if __name__ == "__main__":
    populate_nav_data()
