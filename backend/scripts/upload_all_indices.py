import os
import glob
import requests

API_URL = "http://localhost:8000/api/v1/benchmark-navs/{}/upload"

def upload_all_indices():
    data_dir = "/home/prasad/dev_home/mutual_fund_exp/stock_nivesh_platform/backend/data"
    
    # Target exactly the Merged Master files found in the parent data directory
    merged_files = glob.glob(f"{data_dir}/*_Merged_Master.csv")
    
    if not merged_files:
        print("No optimized Merged Master files found. Please run the merge script first.")
        return
        
    print(f"Found {len(merged_files)} master datasets. Commencing high-fidelity ingestion...")
    
    success = 0
    failures = 0
    
    # Filename → DB benchmark_code overrides for files whose names don't match the registered code
    FILENAME_OVERRIDE_MAP = {
        "NIFTY500_MULTICAP_50_25_50_Merged_Master.csv": "NIFTY500_MULTICAP_50_25_25",
    }

    for file_path in merged_files:
        filename = os.path.basename(file_path)
        # Use override if present, otherwise derive from filename
        benchmark_code = FILENAME_OVERRIDE_MAP.get(
            filename,
            filename.replace("_Merged_Master.csv", "")
        )

        url = API_URL.format(benchmark_code)

        print(f"Uploading: {filename} → {benchmark_code}")
        
        try:
            with open(file_path, 'rb') as f:
                # Use standard multipart form upload
                files = {'file': (filename, f, 'text/csv')}
                resp = requests.post(url, files=files, timeout=60)
                
            if resp.status_code in [200, 201]:
                result = resp.json()
                print(f"  [+] SUCCESS: {result.get('records_inserted', 'Unknown')} nodes stored. Analytics synchronized.")
                success += 1
            else:
                print(f"  [-] FAILURE ({resp.status_code}): {resp.text}")
                failures += 1
        except Exception as e:
            print(f"  [-] ERROR processing {filename}: {e}")
            failures += 1
            
    print("-" * 50)
    print(f"Ingestion Sequence Complete.")
    print(f"  Master Files Processed: {success}")
    print(f"  Errors Logged: {failures}")
    print("-" * 50)

if __name__ == "__main__":
    upload_all_indices()
