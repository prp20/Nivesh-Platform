# Platform Features & Core Engines

This document provides deep-dives into the specialized features and engines that power Nivesh Elite.

---

## 🔄 Stock Data Pipeline

Our platform runs a robust, asynchronous data pipeline that continuously hydrates the database with fresh market and fundamental data.

### Pipeline Architecture
The pipeline has five core stages, orchestrated by `APScheduler`:

1.  **Price Ingestion**: Fetches daily OHLCV from Yahoo Finance.
2.  **Metric Recompute**: Updates price-dependent ratios (PE, PB, PS).
3.  **Technical Analysis**: Generates indicators (SMA, RSI, MACD) using `ta-lib` (C-bindings).
4.  **Fundamental Scraper**: Scheduled weekly scrape of P&L, BS, and Cash Flow from Screener.in.
5.  **Rating Engine**: Generates a 5-dimension composite score (Fundamental, Valuation, Technical, Momentum, Shareholding).

### Key Technical Decisions
- **`ta-lib` (C-bindings)**: Used for high-performance indicator generation over pure Python variants.
- **Idempotency**: All ingestion jobs use `ON CONFLICT DO UPDATE` or `raw_checksum` deduplication.
- **Audit Logging**: Every job is tracked in the `pipeline_audit` table for observability.

---

## 📊 Stock Screener & Ratios

The Screener is the heart of the equity intelligence suite, allowing users to filter stocks through 17+ financial ratios.

### Valuation & Quality Metrics
- **Profitability**: ROE, ROCE, PAT Margin, EBITDA Margin.
- **Growth**: Revenue and PAT growth rates (YoY).
- **Leverage**: Debt-to-Equity and Interest Coverage.
- **Quality**: CFO-to-PAT ratio.

### Advanced Stock Comparison
Users can compare up to 5 equities side-by-side. The engine performs a dynamic join across Price, Ratio, and Rating tables using PostgreSQL **LATERAL JOINs** to ensure sub-second response times even for complex matrices.

---

## 📈 Specialized Engines

For more specific information on our advanced scoring logic, please refer to the following standalone documents:

- **[Fundamental Scoring Design](./fundamental_scoring_design.md)**: Deep dive into how we normalize and score financial statements across sectors.
- **[Sector Specific Scoring](./sector_specific_scoring.md)**: Details on the unique metrics used for Banking and Manufacturing sectors.
