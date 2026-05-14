# pipeline — ingestion pipeline package
# Provides APScheduler jobs and async pipeline classes for all data ingestion.
#
# Module layout:
#   base.py                 — BasePipeline ABC with EtlRun lifecycle management
#   scheduler.py            — APScheduler setup; configure_scheduler() + scheduler instance
#   price_ingestion.py      — yfinance OHLCV ingestion
#   metric_recompute.py     — Price-dependent ratio refresh (PE/PB/PS)
#   technical_analysis.py   — TA-Lib indicator computation
#   rating_engine.py        — Composite stock rating computation
#   fundamental_scraper.py  — Screener.in HTML scraper (financial statements)
#   ratio_engine.py         — Financial ratio computation from statements
