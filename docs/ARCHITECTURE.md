# System Architecture & Design

Nivesh Elite is a professional-grade financial analytics ecosystem designed for high-performance and aesthetic excellence. This document details the technical implementation, from the database schema to the frontend design system.

---

## 🏗️ Technical Overview

The platform follows a modern microservices-inspired architecture with a clear separation between the presentation layer and the analytical backend.

### High-Level Architecture
- **Frontend**: A sleek, dark-mode React application powered by the **Califino** design system.
- **Backend**: A high-performance asynchronous API built with FastAPI, handling complex risk calculations.
- **Data Pipelines**:
  - **MF Engine**: Just-In-Time (JIT) synchronization with AMFI.
  - **Stock Engine**: Multi-stage pipeline for OHLCV ingestion, fundamental scraping, and YoY ratio computation.
- **Database**: PostgreSQL 16, utilizing GIN trigram indexes for full-text search and LATERAL JOINs for high-performance analytics.

---

## 🚀 Backend Design

The backend is an asynchronous powerhouse structured into specialized layers:

### Module Breakdown
- `app/routers/`: API endpoint definitions.
- `app/analytics.py`: Core financial calculation engine for MFs (Sharpe, Sortino, Drawdowns).
- `app/sync.py`: JIT data fetching logic for Mutual Funds.
- `pipeline/`: Equity Data Pipeline (Price ingestion, Fundamental scraping, Ratio engine).
- `app/models.py` & `app/crud.py`: Database schema and ORM operations.

### Analytical Cores
1. **Mutual Fund Analytics**: Computes risk-adjusted returns and capture ratios vs benchmarks.
2. **Equity Ratio Engine**: Vectorized computation of 17 fundamental ratios via Pandas/NumPy.

---

## 🎨 Frontend Architecture

Built for visual excellence and responsive performance.

### Tech Stack
- **Framework**: React 19 (Vite)
- **State Management**: Redux Toolkit (thunks for JIT sync)
- **Styling**: Vanilla CSS with **Califino** tokens (Glassmorphism, CSS Variables)
- **Visualization**: Recharts for performance tracking

### Design System (Califino)
- **Glassmorphism**: 20px blur effects with silver borders (`rgba(69, 70, 76, 0.2)`).
- **Color Palette**: Dark Navy (`#0f1419`) canvas with Gold (`#e9c349`) and Emerald (`#66dd8b`) accents.
- **Micro-animations**: Smooth transitions (300ms) and UI feedback loops for background jobs.

---

## 🐘 Database Schema

### Master Data
- `fund_master`: AMFI codes, scheme names, categories, and fund house details.
- `stocks`: NSE/BSE symbol master with GIN trigram index on `company_name`.
- `benchmark_master`: Market indices mapping.

### Time-Series Data
- `fund_nav_history` / `benchmark_nav_history`: Composite keys `(code, nav_date)`.
- `price_data`: OHLCV daily data from Yahoo Finance.

### Computed Data
- `fund_metrics`: Deep risk/return profiles.
- `financial_statements`: Normalized P&L, BS, and CF stored as **JSONB** for flexibility.
- `financial_ratios`: History of 17 computed fundamental ratios per stock.
- `stock_ratings`: Composite scores across Fundamental, Valuation, and Technical components.

### Performance Optimizations
- **LATERAL JOINs**: Used in screener queries to fetch the latest ratio/price/rating in a single round-trip.
- **JSONB Deduplication**: `raw_checksum` (MD5) prevents redundant writes during re-runs of scrapers.

---

## 🔐 Security
- **JWT Authentication**: Stateless BAerer tokens (HS256).
- **Stateless Auth**: `ENABLE_AUTH` flag for environment-specific security.
- **Role-Based Access**: Specialized `require_admin` dependency for data pipelines.
