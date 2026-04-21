import yfinance as yf
import pandas as pd

tickers = ["^NSEI", "^BSESN", "^NSEBANK", "^CNX100", "NIFTYMIDCAP150.NS"]
df = yf.download(tickers, period="5d", group_by="ticker")
print("Columns structure:")
print(df.columns)
print("\nFirst few rows:")
print(df.head())

for t in tickers:
    try:
        t_df = df[t]
        print(f"\nTicker {t} Columns: {t_df.columns}")
        print(f"Ticker {t} extract (first 1 row):")
        print(t_df.head(1))
    except Exception as e:
        print(f"\nTicker {t} extract FAILED: {e}")
