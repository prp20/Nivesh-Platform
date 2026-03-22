# API & Data Sync Guide

This guide explains how to manage the mutual fund data pipeline.

## 📥 Adding Latest NAVs

### Method 1: Automatic JIT Sync (Recommended)
The system implements **Just-In-Time** fetching. If you request metrics for a fund that hasn't been synced:
```bash
GET /api/v1/metrics/{scheme_code}
```
The backend will automatically:
1. Fetch 3+ years of history from `mftool`.
2. Populate the `fund_nav_history` table.
3. Compute risk metrics and save to `fund_metrics`.

### Method 2: Manual Sync Trigger
To refresh a specific fund's data:
```bash
POST /api/v1/sync/fund/{scheme_code}
```

### Method 3: Global Refresh
To sync all active funds in the database:
```bash
POST /api/v1/sync/all
```

---

## 📊 Analytics Engine

### Forced Recomputation
If you need to recalculate metrics (e.g., after updating calculation logic):
```bash
POST /api/v1/metrics/{scheme_code}/compute
```

---

## 🔐 Administrative CRUD

The backend provides full lifecycle management for fund master data:
- `POST /api/v1/funds/`: Register a new fund.
- `PUT /api/v1/funds/{scheme_code}`: Update fund metadata.
- `DELETE /api/v1/funds/{scheme_code}`: Remove a fund and its history.
