#!/bin/bash

# Master Setup and Data Ingestion Script
# Stock Nivesh Platform

# Set directory to backend root
cd "$(dirname "$0")/.." || exit

echo "=========================================================="
echo "    STOCK NIVESH PLATFORM: DATA INGESTION PIPELINE        "
echo "=========================================================="

# Define Python command (prefer venv)
if [ -f "venv/bin/python3" ]; then
    PYTHON="venv/bin/python3"
else
    PYTHON="python3"
fi

# 1. Initialize Database
echo -e "\n[1/4] Initializing Database Schema..."
$PYTHON scripts/db_init.py
if [ $? -ne 0 ]; then
    echo "!! Database Initialization Failed. Exiting."
    exit 1
fi

# 2. Seed Benchmarks and Indices
echo -e "\n[2/4] Seeding Benchmarks and Index History (NIFTY 100)..."
$PYTHON scripts/seed_indices.py
if [ $? -ne 0 ]; then
    echo "!! Index Seeding Failed. Exiting."
    exit 1
fi

# 3. Seed Mutual Funds Master
echo -e "\n[3/4] Seeding Mutual Fund Master Data from CSV..."
$PYTHON scripts/seed_funds.py
if [ $? -ne 0 ]; then
    echo "!! Mutual Fund Seeding Failed. Exiting."
    exit 1
fi

# 4. Sync NAVs and Metrics
echo -e "\n[4/4] Fetching Historical NAVs and Computing Metrics..."
echo "This step may take time depending on network speed..."
$PYTHON scripts/sync_data.py
if [ $? -ne 0 ]; then
    echo "!! NAV Synchronization Failed. Exiting."
    exit 1
fi

echo -e "\n=========================================================="
echo "    DATA INGESTION COMPLETE: SYSTEM IS READY              "
echo "=========================================================="
