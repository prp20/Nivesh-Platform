import asyncio
import os
import requests
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1"


def get_auth_token() -> str | None:
    """Obtain a JWT by logging in with admin credentials.

    Reads ADMIN_PASSWORD from the environment (falls back to 'admin123' for
    local dev).  Returns None if login fails so the caller can abort.
    """
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    try:
        resp = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": "admin", "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
        print(f"Login failed ({resp.status_code}): {resp.text}")
        return None
    except Exception as e:
        print(f"Login request error: {e}")
        return None


async def recompute_all() -> None:
    print(f"[{datetime.now()}] Initializing Global Metrics Recomputation (Rf = 6.5%)...")

    token = get_auth_token()
    if not token:
        print("Could not obtain auth token. Aborting. Set ADMIN_PASSWORD env var if needed.")
        return

    headers = {"Authorization": f"Bearer {token}"}

    try:
        # 1. Fetch all funds
        resp = requests.get(f"{API_BASE}/funds/?limit=500", headers=headers)
        if resp.status_code != 200:
            print(f"Failed to fetch funds: {resp.status_code}")
            return

        funds = resp.json().get("items", [])
        print(f"Found {len(funds)} assets for analysis.")

        # 2. Trigger compute for each
        for fund in funds:
            code = fund["scheme_code"]
            print(f"Triggering analysis for {code}...")
            trigger_resp = requests.post(
                f"{API_BASE}/metrics/{code}/compute",
                headers=headers,
            )
            if trigger_resp.status_code == 200:
                print(f"Successfully queued {code}")
            else:
                print(f"Failed to queue {code}: {trigger_resp.status_code}")

            # Rate limiting for background tasks
            await asyncio.sleep(2)

    except Exception as e:
        print(f"Error during global recompute: {e}")


if __name__ == "__main__":
    asyncio.run(recompute_all())
