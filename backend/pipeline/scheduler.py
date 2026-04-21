# backend/pipeline/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pipeline.price_ingestion import run_daily_price_ingestion, run_index_ingestion
from pipeline.fundamental_scraper import run_fundamental_scrape_all
from pipeline.ratio_engine import run_ratio_compute_all
from pipeline.metric_recompute import recompute_price_dependent_ratios_all
from pipeline.technical_analysis import run_technical_analysis_all
from pipeline.rating_engine import run_rating_compute_all
from pipeline.stats_ingestion import sync_daily_stats, sync_fundamental_stats

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def configure_scheduler():
    """Register all pipeline jobs with their cron schedules (IST)."""

    # ── Daily jobs (Mon–Fri, after NSE market close) ──────────────────────────

    # 1. Fetch OHLCV for all active stocks
    scheduler.add_job(
        run_daily_price_ingestion,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=30),
        max_instances=1,
        id="price_daily",
    )

    # 3. Fetch live stats from yfinance (Market Cap, 52w range, P/B, Div Yield)
    scheduler.add_job(
        sync_daily_stats,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=50),
        max_instances=1,
        id="stats_daily_yf",
    )

    # 4. Recompute price-dependent ratios (PE, PS)
    #    Runs AFTER prices are ingested. Does NOT touch quarterly metrics.
    scheduler.add_job(
        recompute_price_dependent_ratios_all,
        CronTrigger(day_of_week="mon-fri", hour=19, minute=0),
        max_instances=1,
        id="price_ratio_refresh",
    )

    # 4. Compute technical indicators (SMA, EMA, RSI, MACD, Bollinger, ATR, ADX, Stoch)
    scheduler.add_job(
        run_technical_analysis_all,
        CronTrigger(day_of_week="mon-fri", hour=19, minute=30),
        max_instances=1,
        id="technical_analysis_daily",
    )

    # 5. Compute composite stock ratings (fundamental + valuation + technical + momentum + shareholding)
    scheduler.add_job(
        run_rating_compute_all,
        CronTrigger(day_of_week="mon-fri", hour=20, minute=15),
        max_instances=1,
        id="rating_compute_daily",
    )

    # ── Weekly jobs (Sunday) ──────────────────────────────────────────────────

    # 6. Scrape screener.in fundamentals for stocks not updated in 90+ days
    scheduler.add_job(
        run_fundamental_scrape_all,
        CronTrigger(day_of_week="sun", hour=2, minute=0),
        max_instances=1,
        id="fundamental_scrape_weekly",
    )

    # 7. Recompute quarterly ratios (ROE, ROCE, D/E, margins, etc.) after scrape
    scheduler.add_job(
        run_ratio_compute_all,
        CronTrigger(day_of_week="sun", hour=9, minute=0),
        max_instances=1,
        id="ratio_compute_weekly",
    )
    # 8. Sync deep fundamental stats from yfinance (ROE, ROA, Debt/Equity, etc.)
    scheduler.add_job(
        sync_fundamental_stats,
        CronTrigger(day_of_week="sun", hour=10, minute=0),
        max_instances=1,
        id="stats_fundamental_yf_weekly",
    )

    # ── DEFERRED — Future Phase ───────────────────────────────────────────────
    # Pattern detection (Head & Shoulders, Double Top, Support/Resistance)
    # is deferred to a later phase. DetectedPattern table is reserved.
    # scheduler.add_job(run_pattern_detection, CronTrigger(day_of_week="mon-fri", hour=20, minute=45), id="pattern_detection")
