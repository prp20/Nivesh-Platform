import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_compare(codes, expected_status=200):
    url = f"{BASE_URL}/funds/compare?codes={','.join(codes)}"
    print(f"Testing: {url}")
    try:
        response = requests.get(url)
        print(f"Status: {response.status_code}")
        if response.status_code == expected_status:
            print("✅ Success")
            if response.status_code == 200:
                data = response.json()
                print(f"Funds returned: {len(data)}")
        else:
            print(f"❌ Failed (Expected {expected_status}, got {response.status_code})")
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    print("-" * 50)

if __name__ == "__main__":
    # Note: These codes should exist in your DB. 
    # I'll use common ones if available or expect 404/400 for invalid ones to test logic.
    
    # 1. Test with < 2 codes (Expected 400)
    test_compare(["100033"], 400)
    
    # 2. Test with > 4 codes (Expected 400)
    test_compare(["1", "2", "3", "4", "5"], 400)
    
    # 4. Test with real codes (Expected 200)
    real_codes = ["111549", "118269", "118275", "118278"]
    test_compare(real_codes, 200)
