import httpx
import asyncio

async def test_filters():
    base_url = "http://localhost:8000/api/v1/funds"
    
    print("\n--- Testing Subcategory Filter (Large Cap) ---")
    async with httpx.AsyncClient() as client:
        # Test 1: Subcategory filtering for Large Cap
        resp = await client.get(f"{base_url}/", params={"subcategory": "Large Cap", "limit": 5})
        if resp.status_code == 200:
            data = resp.json()
            print(f"Total found: {data['total']}")
            for item in data['items']:
                print(f"- {item['scheme_name']} ({item['scheme_subcategory']})")
        else:
            print(f"Error: {resp.status_code}")

        print("\n--- Testing Benchmark Filter (NIFTY 100) ---")
        # Test 2: Benchmark filtering
        resp = await client.get(f"{base_url}/", params={"benchmark_code": "NIFTY 100", "limit": 5})
        if resp.status_code == 200:
            data = resp.json()
            print(f"Total found: {data['total']}")
            for item in data['items']:
                # Note: benchmark_index_code might not be in the read schema, 
                # but we can verify the results if we had it.
                print(f"- {item['scheme_name']}")
        else:
            print(f"Error: {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(test_filters())
