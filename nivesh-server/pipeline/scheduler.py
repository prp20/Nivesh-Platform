"""
pipeline/scheduler.py — APScheduler setup for all ingestion jobs.

Exports:
    scheduler          — AsyncIOScheduler instance (started/stopped by app/main.py lifespan)
    configure_scheduler() — registers all 7 cron jobs; called once at startup

Job dependency chain (IST):
    19:00  yf_price (Mon–Fri)
              ↓
    20:00  technical_analysis (Mon–Fri)
              ↓
    21:00  stock_ratings

    19:30  benchmark_nav ──┐
    21:30  amfi_nav ────────┤
                            ↓
    23:00  fund_metrics

    06:00 Sun  screener_fundamentals  (weekly, no strict dependency)

All jobs use:
    replace_existing=True   — safe to call configure_scheduler() more than once
    misfire_grace_time=600  — if the instance was briefly unavailable, fires within 10 min
    coalesce=True           — if missed multiple fires, run only once on recovery
"""

import logging
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

# Single scheduler instance — imported and started by app/main.py lifespan
scheduler = AsyncIOScheduler(timezone=IST)


def configure_scheduler() -> None:
    """
    Register all pipeline cron jobs.

    Called once during FastAPI lifespan startup (app/main.py).
    Each job is a standalone async function that creates its own DB session.
    """

    # ── Mutual Fund pipelines ────────────────────────────────────────────────

    scheduler.add_job(
        _run_benchmark_nav,
        trigger=CronTrigger(hour=19, minute=30, timezone=IST),
        id="benchmark_nav",
        name="Benchmark NAV daily sync",
        replace_existing=True,
        misfire_grace_time=600,
        coalesce=True,
    )

    scheduler.add_job(
        _run_amfi_nav,
        trigger=CronTrigger(hour=21, minute=30, timezone=IST),
        id="amfi_nav",
        name="AMFI fund NAV daily sync",
        replace_existing=True,
        misfire_grace_time=600,
        coalesce=True,
    )

    scheduler.add_job(
        _run_fund_metrics,
        trigger=CronTrigger(hour=23, minute=0, timezone=IST),
        id="fund_metrics",
        name="Fund + benchmark metrics recompute",
        replace_existing=True,
        misfire_grace_time=600,
        coalesce=True,
    )

    # ── Stock pipelines ───────────────────────────────────────────────────────

    scheduler.add_job(
        _run_yf_price,
        trigger=CronTrigger(day_of_week="mon-fri", hour=19, minute=0, timezone=IST),
        id="yf_price",
        name="Yahoo Finance price ingestion",
        replace_existing=True,
        misfire_grace_time=600,
        coalesce=True,
    )

    scheduler.add_job(
        _run_technical_analysis,
        trigger=CronTrigger(day_of_week="mon-fri", hour=20, minute=0, timezone=IST),
        id="technical_analysis",
        name="TA-Lib technical indicator computation",
        replace_existing=True,
        misfire_grace_time=600,
        coalesce=True,
    )

    scheduler.add_job(
        _run_stock_ratings,
        trigger=CronTrigger(hour=21, minute=0, timezone=IST),
        id="stock_ratings",
        name="Stock rating computation",
        replace_existing=True,
        misfire_grace_time=600,
        coalesce=True,
    )

    scheduler.add_job(
        _run_screener_fundamentals,
        trigger=CronTrigger(day_of_week="sun", hour=6, minute=0, timezone=IST),
        id="screener_fundamentals",
        name="Screener.in financial statements scrape",
        replace_existing=True,
        misfire_grace_time=3600,  # 1-hour grace — weekly job, timing is flexible
        coalesce=True,
    )

    job_count = len(scheduler.get_jobs())
    logger.info(f"Scheduler configured — {job_count} jobs registered")


# ── Job wrapper functions ────────────────────────────────────────────────────
# Each function creates its own DB session and delegates to the pipeline class.
# Defined here (not inline lambdas) so APScheduler can serialize job state.

async def _run_benchmark_nav() -> None:
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        from pipeline.price_ingestion import _run_benchmark_nav_pipeline
        await _run_benchmark_nav_pipeline(db)


async def _run_amfi_nav() -> None:
    """Delegates to the existing AMFI sync logic in app/sync.py."""
    from app.database import AsyncSessionLocal
    from app import crud
    async with AsyncSessionLocal() as db:
        run, created = await crud.start_etl_run(db, pipeline_name="amfi_nav", triggered_by="scheduler")
        if not created:
            logger.warning("[amfi_nav] already RUNNING — skipping")
            return
        try:
            from pipeline.price_ingestion import _sync_amfi_navs
            records_out = await _sync_amfi_navs(db)
            await crud.finish_etl_run(db, run.id, "COMPLETED", records_out=records_out)
        except Exception as exc:
            logger.exception("[amfi_nav] failed")
            await crud.finish_etl_run(db, run.id, "FAILED", error_msg=str(exc)[:1000])


async def _run_fund_metrics() -> None:
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        from pipeline.metric_recompute import _run_fund_metrics_pipeline
        await _run_fund_metrics_pipeline(db)


async def _run_yf_price() -> None:
    from pipeline.price_ingestion import run_daily_price_ingestion
    await run_daily_price_ingestion()


async def _run_technical_analysis() -> None:
    from pipeline.technical_analysis import run_technical_analysis_all
    await run_technical_analysis_all()


async def _run_stock_ratings() -> None:
    from pipeline.rating_engine import run_rating_compute_all
    await run_rating_compute_all()


async def _run_screener_fundamentals() -> None:
    from pipeline.fundamental_scraper import run_fundamental_scrape_all
    await run_fundamental_scrape_all(days_since_last=90)
