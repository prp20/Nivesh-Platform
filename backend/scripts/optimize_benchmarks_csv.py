import pandas as pd
import os

def update_benchmarks(csv_path):
    print(f"Reading CSV from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Mapping Dictionary
    category_map = {
        "ELSS": "NIFTY_500",
        "Flexi Cap Fund": "NIFTY_500",
        "Focused Fund": "NIFTY_500",
        "Large & Mid Cap Fund": "NIFTY_LARGEMIDCAP_250",
        "Large Cap Fund": "NIFTY_100",
        "Mid Cap Fund": "NIFTY_MIDCAP_150",
        "Multi Cap Fund": "NIFTY_MULTICAP_500_50_25_50",
        "Small Cap Fund": "NIFTY_SMALLCAP_250",
    }
    
    def get_benchmark(row):
        name = str(row['scheme_name']).lower()
        subcategory = str(row['scheme_subcategory'])
        
        # 1. Name-based overrides (High Priority)
        if "nifty 50 index" in name or "nifty 50 etf" in name:
            return "NIFTY_50"
        if "nifty 100 index" in name or "nifty 100 etf" in name:
            return "NIFTY_100"
        if "nifty 500 index" in name:
            return "NIFTY_500"
        if "nifty midcap 150 index" in name:
            return "NIFTY_MIDCAP_150"
        if "nifty smallcap 250 index" in name:
            return "NIFTY_SMALLCAP_250"
        if "nifty next 50" in name:
            return "NIFTY_NEXT_50" # Not in our DB yet, but accurate research
            
        # 2. Category-based mapping
        return category_map.get(subcategory, "NIFTY_500") # Default to Nifty 500 for broad equity

    print("Applying precision benchmark mapping...")
    df['benchmark_index_code'] = df.apply(get_benchmark, axis=1)
    
    # Final cleanup: ensure we don't use benchmarks we haven't imported if we can avoid it
    # Currently imported: NIFTY_50, NIFTY_100, NIFTY_500, NIFTY_LARGEMIDCAP_250, NIFTY_MIDCAP_150, NIFTY_SMALLCAP_250, NIFTY_MULTICAP_500_50_25_50
    valid_codes = [
        "NIFTY_50", "NIFTY_100", "NIFTY_500", "NIFTY_LARGEMIDCAP_250", 
        "NIFTY_MIDCAP_150", "NIFTY_SMALLCAP_250", "NIFTY_MULTICAP_500_50_25_50"
    ]
    
    # If we mapped to something not yet in our system (like NEXT_50), fallback to closest broad market
    df['benchmark_index_code'] = df['benchmark_index_code'].apply(lambda x: x if x in valid_codes else "NIFTY_500")

    print(f"Saving updated CSV to {csv_path}...")
    df.to_csv(csv_path, index=False)
    print("Optimization Complete.")

if __name__ == "__main__":
    csv_file = "/home/prasad/dev_home/mutual_fund_exp/stock_nivesh_platform/backend/data/new_equity_only.csv"
    update_benchmarks(csv_file)
