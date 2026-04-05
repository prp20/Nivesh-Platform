#!/usr/bin/env python3
"""
Simple synchronous API endpoint test suite.
Tests all routes without pytest complexity.
"""

import requests
import json
from typing import Tuple

BASE_URL = "http://localhost:8000/api/v1"
ISSUES_FOUND = []
ENDPOINTS_TESTED = 0

def test_endpoint(method: str, path: str, expected_status: int | list,
                  auth_token=None, data=None, form_data=None, name="") -> bool:
    """Test a single endpoint."""
    global ENDPOINTS_TESTED
    ENDPOINTS_TESTED += 1

    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            if form_data:
                # For form data (like auth login)
                response = requests.post(url, data=form_data, timeout=5)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=5)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=5)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=5)
        else:
            return False

        expected = expected_status if isinstance(expected_status, list) else [expected_status]
        status_ok = response.status_code in expected

        symbol = "✓" if status_ok else "✗"
        print(f"{symbol} {method:6} {path:50} → {response.status_code:3}")

        if not status_ok:
            ISSUES_FOUND.append({
                "endpoint": f"{method} {path}",
                "expected": expected,
                "got": response.status_code,
                "body": response.text[:200]
            })

        return status_ok
    except Exception as e:
        print(f"✗ {method:6} {path:50} → ERROR: {str(e)[:50]}")
        ISSUES_FOUND.append({
            "endpoint": f"{method} {path}",
            "error": str(e)[:200]
        })
        return False


def get_token():
    """Get auth token."""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


def main():
    print("\n" + "=" * 80)
    print("NIVESH BACKEND API — COMPREHENSIVE ENDPOINT TEST SUITE")
    print("=" * 80 + "\n")

    # Get auth token
    token = get_token()
    print(f"Auth Token: {'✓ Obtained' if token else '✗ Failed'}\n")

    print("─" * 80)
    print("HEALTH & ROOT ENDPOINTS")
    print("─" * 80)
    test_endpoint("GET", "/health", 200)

    print("\n" + "─" * 80)
    print("AUTH ENDPOINTS")
    print("─" * 80)
    test_endpoint("POST", "/auth/login", 200,
                 form_data={"username": "admin", "password": "admin123"})
    test_endpoint("POST", "/auth/login", 401,
                 form_data={"username": "admin", "password": "wrong"})
    test_endpoint("GET", "/auth/me", [200, 401])
    test_endpoint("GET", "/auth/me", 200, auth_token=token)

    print("\n" + "─" * 80)
    print("FUNDS ENDPOINTS")
    print("─" * 80)
    test_endpoint("GET", "/funds/", 200)
    test_endpoint("GET", "/funds/?skip=0&limit=10", 200)
    test_endpoint("GET", "/funds/?category=Equity", 200)
    test_endpoint("GET", "/funds/119533", [200, 404])
    test_endpoint("GET", "/funds/119533/similar", [200, 404])
    test_endpoint("GET", "/funds/compare?codes=1,2", [200, 400])
    test_endpoint("POST", "/funds/", 201, auth_token=token,
                 data={
                     "scheme_code": "TEST001",
                     "scheme_name": "Test Fund",
                     "amc_name": "Test AMC",
                     "inception_date": "2024-01-01",
                     "plan_type": "Direct",
                     "scheme_category": "Equity"
                 })
    test_endpoint("POST", "/funds/", [201, 401],
                 data={
                     "scheme_code": "TEST002",
                     "scheme_name": "Test Fund 2",
                     "amc_name": "Test AMC",
                     "inception_date": "2024-01-01",
                     "plan_type": "Direct",
                     "scheme_category": "Equity"
                 })
    test_endpoint("PUT", "/funds/119533", [200, 404], auth_token=token,
                 data={"scheme_name": "Updated"})
    test_endpoint("DELETE", "/funds/119533", [204, 404], auth_token=token)

    print("\n" + "─" * 80)
    print("BENCHMARKS ENDPOINTS")
    print("─" * 80)
    test_endpoint("GET", "/benchmarks/", 200)
    test_endpoint("GET", "/benchmarks/NIFTY50", [200, 404])
    test_endpoint("POST", "/benchmarks/", 201, auth_token=token,
                 data={
                     "benchmark_code": "TEST_BENCH",
                     "benchmark_name": "Test Benchmark",
                     "ticker": "TEST"
                 })
    test_endpoint("POST", "/benchmarks/", [201, 401],
                 data={
                     "benchmark_code": "TEST_BENCH2",
                     "benchmark_name": "Test Benchmark 2",
                     "ticker": "TEST2"
                 })
    test_endpoint("PUT", "/benchmarks/NIFTY50", [200, 404], auth_token=token,
                 data={"benchmark_name": "Updated"})
    test_endpoint("DELETE", "/benchmarks/NIFTY50", [204, 404], auth_token=token)

    print("\n" + "─" * 80)
    print("NAV ENDPOINTS")
    print("─" * 80)
    test_endpoint("GET", "/navs/119533", 200)
    test_endpoint("GET", "/navs/119533?limit=50", 200)
    test_endpoint("GET", "/navs/119533?limit=9999", [200, 422])
    test_endpoint("POST", "/navs/119533/bulk", 201, auth_token=token,
                 data={"data": {"2024-01-01": 100.5}})
    test_endpoint("POST", "/navs/119533/bulk", [201, 401],
                 data={"data": {"2024-01-01": 100.5}})

    print("\n" + "─" * 80)
    print("BENCHMARK NAV ENDPOINTS")
    print("─" * 80)
    test_endpoint("GET", "/benchmark-navs/NIFTY50", 200)
    test_endpoint("POST", "/benchmark-navs/NIFTY50/bulk", 201, auth_token=token,
                 data={"data": {"2024-01-01": 19000.0}})

    print("\n" + "─" * 80)
    print("METRICS ENDPOINTS")
    print("─" * 80)
    test_endpoint("GET", "/metrics/119533", 200)
    test_endpoint("GET", "/metrics/119533/status", 200)
    test_endpoint("GET", "/metrics/!!!invalid!!!", 400)
    test_endpoint("POST", "/metrics/119533/compute", 200, auth_token=token)
    test_endpoint("POST", "/metrics/119533/compute", [200, 401])

    print("\n" + "─" * 80)
    print("SYNC ENDPOINTS")
    print("─" * 80)
    test_endpoint("POST", "/sync/119533", 200, auth_token=token)
    test_endpoint("POST", "/sync/119533", [200, 401])
    test_endpoint("POST", "/sync/all", 200, auth_token=token)
    test_endpoint("POST", "/sync/all", [200, 401])

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Endpoints Tested: {ENDPOINTS_TESTED}")
    print(f"Issues Found: {len(ISSUES_FOUND)}\n")

    if ISSUES_FOUND:
        print("ISSUES DETECTED:")
        for i, issue in enumerate(ISSUES_FOUND, 1):
            print(f"\n{i}. {issue['endpoint']}")
            if 'expected' in issue:
                print(f"   Expected: {issue['expected']}, Got: {issue['got']}")
            if 'error' in issue:
                print(f"   Error: {issue['error']}")
            if 'body' in issue:
                print(f"   Response: {issue['body']}")
    else:
        print("✓ ALL TESTS PASSED - No issues detected!")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
