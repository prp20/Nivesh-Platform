from mftool import Mftool
import json

def debug_fund(scheme_code):
    mf = Mftool()
    print(f"Checking fund {scheme_code}...")
    
    try:
        print("1. Fetching historical NAV...")
        nav = mf.get_scheme_historical_nav(scheme_code)
        if nav:
            print(f"Successfully fetched {len(nav)} records.")
        else:
            print("NAV returned None or empty.")
            
        print("2. Fetching scheme details...")
        details = mf.get_scheme_details(scheme_code)
        print("Details successfully fetched.")
        # print(json.dumps(details, indent=2))
        
    except Exception as e:
        print(f"FAILED with error: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    debug_fund("120505")
