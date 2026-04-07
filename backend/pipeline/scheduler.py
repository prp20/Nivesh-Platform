# backend/pipeline/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def configure_scheduler():
    """Register all pipeline jobs. Jobs are no-ops until their modules are implemented."""
    # Prices — Mon-Fri after NSE market close (15:30 IST = 18:30 UTC)
    # scheduler.add_job(run_daily_price_ingestion,  CronTrigger(day_of_week="mon-fri", hour=18, minute=30))
    # scheduler.add_job(run_index_ingestion,         CronTrigger(day_of_week="mon-fri", hour=18, minute=40))
    # scheduler.add_job(run_technical_indicators,   CronTrigger(day_of_week="mon-fri", hour=19, minute=0))
    # scheduler.add_job(run_pattern_detection,       CronTrigger(day_of_week="mon-fri", hour=19, minute=45))
    # scheduler.add_job(run_rating_compute,          CronTrigger(day_of_week="mon-fri", hour=20, minute=15))
    # scheduler.add_job(run_fundamental_scrape_all,  CronTrigger(day_of_week="sun",     hour=2,  minute=0))
    # scheduler.add_job(run_ratio_compute_all,       CronTrigger(day_of_week="sun",     hour=9,  minute=0))
    # scheduler.add_job(run_shareholding_scrape,     CronTrigger(day=1,                 hour=3,  minute=0))
    # scheduler.add_job(run_data_integrity_check,    CronTrigger(day_of_week="mon-fri", hour=9,  minute=0))
    pass  # Uncomment each line as the corresponding module is implemented
