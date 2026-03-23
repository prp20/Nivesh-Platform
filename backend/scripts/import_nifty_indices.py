import os
import csv
import requests
from datetime import datetime
from pathlib import Path

API_BASE = "http://localhost:8000/api/v1"
DATA_DIR = Path("backend/data/Nifty_indices")

# Mapping directory names to benchmark codes/names
INDEX_MAPPING = {
    "NIFTY_100": {"name": "NIFTY 100", "type": "Broad Market"},
    "NIFTY_500": {"name": "NIFTY 500", "type": "Broad Market"},
    "NIFTY_LARGEMIDCAP_250": {"name": "NIFTY LARGEMIDCAP 250", "type": "Multi Cap"},
    "NIFTY_MIDCAP_150": {"name": "NIFTY MIDCAP 150", "type": "Mid Cap"},
    "NIFTY_MULTICAP_500_50_25_50": {"name": "NIFTY MULTICAP 500 50:25:25", "type": "Multi Cap"},
    "NIFTY_SMALLCAP_250": {"name": "NIFTY SMALLCAP 250", "type": "Small Cap"},
}

def register_benchmark(code, name, b_type):
    payload = {
        "benchmark_code": code,
        "benchmark_name": name,
        "ticker": code,
        "benchmark_type": b_type,
        "asset_class": "Equity",
        "is_active": True
    }
    try:
        resp = requests.post(f"{API_BASE}/benchmarks/", json=payload)
        if resp.status_code in [200, 201]:
            print(f"Registered benchmark: {name}")
        else:
            print(f"Benchmark {name} already exists or error: {resp.status_code}")
    except Exception as e:
        print(f"Error registering {name}: {e}")

def parse_date(date_str):
    # Input: "23 Feb 2026"
    try:
        return datetime.strptime(date_str.strip(), "%d %b %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None

def import_index_data(dir_path, code):
    all_data = {}
    csv_files = list(dir_path.glob("*.csv"))
    print(f"Processing {len(csv_files)} files for {code}...")
    
    for csv_file in csv_files:
        with open(csv_file, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Keys might have extra spaces or quotes based on the file inspection
                # "Index Name","Date","Open","High","Low","Close"
                date_val = row.get("Date") or row.get("date")
                close_val = row.get("Close") or row.get("close")
                
                if not date_val or not close_val:
                    continue
                    
                iso_date = parse_date(date_val)
                if iso_date:
                    try:
                        all_data[iso_date] = float(close_val.replace(",", ""))
                    except ValueError:
                        continue

    if all_data:
        print(f"Uploading {len(all_data)} records for {code}...")
        try:
            resp = requests.post(
                f"{API_BASE}/benchmark-navs/{code}/bulk", 
                json={"data": all_data}
            )
            if resp.status_code in [200, 201]:
                print(f"Successfully imported {code}")
            else:
                print(f"Failed to import {code}: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Error uploading {code}: {e}")

def main():
    if not DATA_DIR.exists():
        print(f"Data directory {DATA_DIR} not found!")
        return

    for dir_name, info in INDEX_MAPPING.items():
        dir_path = DATA_DIR / dir_name
        if dir_path.exists():
            register_benchmark(dir_name, info["name"], info["type"])
            import_index_data(dir_path, dir_name)
        else:
            print(f"Warning: Folder {dir_name} not found in {DATA_DIR}")

if __name__ == "__main__":
    main()
