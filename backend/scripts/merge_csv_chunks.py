import os
import sys
import glob
import pandas as pd

def merge_nifty_csvs():
    target_dir = sys.argv[1]
    csv_files = glob.glob(os.path.join(target_dir, "*.csv"))
    
    # Strip out any potential previous merged outputs to prevent infinite recursion sizing
    csv_files = [f for f in csv_files if "Merged" not in f]
    
    if not csv_files:
        print("No fragmented CSVs detected in target directory.")
        return
        
    print(f"Discovered {len(csv_files)} historical fragment files. Initiating Pandas merge protocol...")
    
    dataframes = []
    for f in csv_files:
        df = pd.read_csv(f)
        # Standardize strictly incase columns have trailing spaces
        df.columns = [c.strip().replace('"', '') for c in df.columns]
        dataframes.append(df)
        
    master_df = pd.concat(dataframes, ignore_index=True)
    
    # Convert native 'Date' strings ("23 Feb 2010") to proper datetime nodes
    print("Normalizing date vectors and executing chronological sort...")
    master_df['Date_Ordinal'] = pd.to_datetime(master_df['Date'])
    
    # Sort chronologically (oldest to newest)
    master_df = master_df.sort_values(by='Date_Ordinal', ascending=True)
    
    # Drop overlapping records based strictly on the Date index to maintain pure timeseries
    master_df = master_df.drop_duplicates(subset=['Date'])
    
    # Drop the temporary calculation matrix
    master_df = master_df.drop(columns=['Date_Ordinal'])
    base_file = sys.argv[1].split("/")[-1]
    output_path = os.path.join(target_dir, f"{base_file}_Merged_Master.csv")
    master_df.to_csv(output_path, index=False)
    
    print("--------------------------------------------------")
    print(f"[+] SUCCESS: Time-series reconstructed.")
    print(f"    Total Chronological Nodes: {len(master_df)}")
    print(f"    Output Path: {output_path}")
    print("--------------------------------------------------")

if __name__ == "__main__":
    merge_nifty_csvs()
