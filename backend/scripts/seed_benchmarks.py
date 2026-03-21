import requests

API_BASE = "http://localhost:8000/api/v1"

BENCHMARKS = [
    {
        "benchmark_code": "NIFTY50",
        "benchmark_name": "NIFTY 50",
        "ticker": "^NSEI",
        "benchmark_type": "Broad Market",
        "asset_class": "Equity"
    },
    {
        "benchmark_code": "NIFTYNEXT50",
        "benchmark_name": "NIFTY NEXT 50",
        "ticker": "^NSMID",
        "benchmark_type": "Broad Market",
        "asset_class": "Equity"
    },
    {
        "benchmark_code": "NIFTYMIDCAP150",
        "benchmark_name": "NIFTY MIDCAP 150",
        "ticker": "NIFTY_MIDCAP_150",
        "benchmark_type": "Midcap",
        "asset_class": "Equity"
    },
    {
        "benchmark_code": "NIFTYSMALLCAP250",
        "benchmark_name": "NIFTY SMALLCAP 250",
        "ticker": "NIFTY_SMALLCAP_250",
        "benchmark_type": "Smallcap",
        "asset_class": "Equity"
    }
]

def seed_benchmarks():
    print("Seeding Benchmarks...")
    for b in BENCHMARKS:
        try:
            resp = requests.post(f"{API_BASE}/benchmarks/", json=b)
            if resp.status_code in [200, 201]:
                print(f"Successfully seeded {b['benchmark_name']}")
            else:
                print(f"Failed to seed {b['benchmark_name']}: {resp.text}")
        except Exception as e:
            print(f"Error seeding {b['benchmark_name']}: {e}")

if __name__ == "__main__":
    seed_benchmarks()
