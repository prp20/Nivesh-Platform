"""
seed_historical_data.py — One-time full historical data load for Nivesh Platform.

Runs all seeding phases in dependency order:

  Phase 1 — Master data + benchmark NAV history
    1a. benchmark_master     (from data/indices.csv)
    1b. stocks               (from data/stocks.csv + data/indices.csv)
    1c. fund_master          (from data/scheme_master_with_benchmark.csv)
    1d. benchmark_nav_history (from Yahoo Finance)

  Phase 2 — Mutual fund NAV history + metrics
    2.  fund_nav_history + fund_metrics  (from AMFI via mftool)
        Runtime: ~30–60 min for all active funds (sequential, 1 s delay per fund)

  Phase 3 — Stock OHLCV price history
    3.  price_data  (from Yahoo Finance via yfinance)
        Runtime: ~20–40 min for ~500 stocks (batched, 1.5 s delay per batch)

Prerequisites:
  - alembic upgrade head must have been run
  - pip install "yfinance>=0.2.40" mftool psycopg2-binary tqdm

Usage:
  cd nivesh-server
  export DATABASE_URL="postgresql://postgres.[ref]:[pwd]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"

  # Full load (all history)
  python scripts/seed_historical_data.py

  # Limit history window (faster for dev)
  python scripts/seed_historical_data.py --nav-period 1y --price-period 2y

  # Skip phases you already ran
  python scripts/seed_historical_data.py --skip-master --skip-nav

  # Preview without writing
  python scripts/seed_historical_data.py --dry-run

Flags:
  --nav-period    yfinance period for benchmark NAV: 1y/5y/10y/max  (default: max)
  --price-period  yfinance period for stock prices: 1y/2y/3y/5y/10y/max  (default: 5y)
  --fund-period   mftool period for fund NAV: 1y/3y/5y/max  (default: max)
  --skip-master   Skip Phase 1 (master data + benchmark NAV)
  --skip-nav      Skip Phase 2 (fund NAV history + metrics)
  --skip-prices   Skip Phase 3 (stock price history)
  --dry-run       Preview row counts without writing to DB
  --batch-size    Stocks per yfinance batch (default: 20)
"""

import sys
import os
import argparse
import time

# Ensure imports resolve when run from inside nivesh-server/
_script_dir = os.path.dirname(os.path.abspath(__file__))
_server_root = os.path.dirname(_script_dir)  # nivesh-server/
if _server_root not in sys.path:
    sys.path.insert(0, _server_root)

# ── Seed sub-modules ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(_script_dir, "seed"))

import seed_benchmarks
import seed_stocks
import seed_funds
import seed_benchmark_nav
import seed_stock_prices


# ── Fund NAV sync (uses sync_data.py logic inline) ───────────────────────────

def run_fund_nav_sync(period: str, dry_run: bool):
    """
    Sync full NAV history + recompute metrics for all active funds via mftool.
    Implemented inline here to avoid subprocess overhead and give unified progress.
    """
    import json
    import logging
    from datetime import datetime, timezone
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from mftool import Mftool
    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None

    # Late import to avoid errors if app/ isn't on path
    from app import analytics, models, config

    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger("fund_nav_sync")

    db_url = config.settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(db_url)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    mf = Mftool()

    def pd_to_date(date_str):
        for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    def sync_one(session, scheme_code: str, period: str) -> tuple[bool, str]:
        try:
            fund = session.query(models.FundMaster).filter_by(scheme_code=scheme_code).first()
            if not fund:
                return False, "Not in fund_master"

            # Fetch NAV from AMFI
            raw = None
            for attempt in range(3):
                try:
                    raw = json.loads(mf.get_scheme_historical_nav(scheme_code, as_json=True))
                    if raw and "data" in raw and raw["data"]:
                        break
                    raw = None
                except Exception as e:
                    if attempt < 2:
                        time.sleep(2)
                    else:
                        return False, f"AMFI fetch failed: {e}"

            if not raw:
                return False, "Empty response from AMFI"

            nav_list = raw["data"]

            # Period filter
            import pandas as pd
            limit_date = None
            if period != "max":
                try:
                    years = int(period.replace("y", ""))
                    limit_date = datetime.now().date() - pd.Timedelta(days=years * 365.25)
                except Exception:
                    pass

            rows = []
            for item in nav_list:
                d = pd_to_date(str(item.get("date", "")))
                v = item.get("nav")
                if d and v:
                    try:
                        nav_val = float(v)
                        if nav_val > 0 and (limit_date is None or d >= limit_date):
                            rows.append({"scheme_code": scheme_code, "nav_date": d, "nav_value": nav_val})
                    except (ValueError, TypeError):
                        continue

            if not rows:
                return False, f"No valid NAVs for period={period}"

            if not dry_run:
                stmt = pg_insert(models.FundNavHistory).values(rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["scheme_code", "nav_date"],
                    set_={"nav_value": stmt.excluded.nav_value},
                )
                session.execute(stmt)

                # Compute metrics
                nav_history = [{"nav_date": r["nav_date"], "nav_value": r["nav_value"]} for r in rows]
                bench_history = []
                if fund.benchmark_index_code:
                    bench_recs = session.query(models.BenchmarkNavHistory).filter_by(
                        benchmark_code=fund.benchmark_index_code
                    ).all()
                    bench_history = [{"nav_date": b.nav_date, "index_value": float(b.index_value)} for b in bench_recs]

                calc = analytics.compute_all_metrics(nav_history, bench_history)
                if calc and "current_nav" in calc:
                    def to_f(v):
                        if v is None:
                            return None
                        try:
                            return float(v.item()) if hasattr(v, "item") else float(v)
                        except Exception:
                            return None

                    mapping = {
                        "sharpe": "sharpe_ratio", "sortino": "sortino_ratio",
                        "std_dev": "standard_deviation", "max_drawdown": "maximum_drawdown",
                    }
                    metric_fields = [
                        "cagr_3year", "cagr_5year", "absolute_return_1y", "absolute_return_3y",
                        "absolute_return_5y", "absolute_return_10y", "short_term_return_6m",
                        "upside_capture", "downside_capture", "sortino_ratio", "sharpe_ratio",
                        "alpha", "beta", "standard_deviation", "maximum_drawdown",
                        "tracking_error", "information_ratio", "data_completeness_percentage",
                    ]
                    payload = {
                        "scheme_code": scheme_code,
                        "current_nav": to_f(calc["current_nav"]),
                        "nav_date": calc["nav_date"],
                        "aum_in_crores": 0.0,
                        "calculation_period_start_date": calc.get("calculation_period_start_date"),
                        "calculation_period_end_date": calc.get("calculation_period_end_date"),
                        "has_sufficient_data": bool(calc.get("has_sufficient_data", True)),
                        "final_verdict": calc.get("final_verdict"),
                        "metrics_calculated_at": datetime.now(timezone.utc),
                    }
                    for field in metric_fields:
                        src = next((k for k, v in mapping.items() if v == field), field)
                        payload[field] = to_f(calc.get(src))

                    stmt_m = pg_insert(models.FundMetrics).values(payload)
                    stmt_m = stmt_m.on_conflict_do_update(
                        index_elements=["scheme_code"],
                        set_={k: v for k, v in payload.items() if k != "scheme_code"},
                    )
                    session.execute(stmt_m)

                session.commit()

            return True, f"{len(rows)} NAV records"

        except Exception as e:
            session.rollback()
            return False, str(e)

    with Session() as session:
        funds = session.query(models.FundMaster).filter_by(is_active=True).all()

    if not funds:
        print("  No active funds found — run Phase 1 first.")
        return

    print(f"  {len(funds)} active funds  (period={period}){'  [DRY RUN]' if dry_run else ''}")

    fail_count = 0
    ok_count   = 0
    iter_funds = tqdm(funds, desc="  Funds", unit="fund") if tqdm else funds

    for fund in iter_funds:
        with Session() as session:
            ok, msg = sync_one(session, fund.scheme_code, period)
        if ok:
            ok_count += 1
        else:
            fail_count += 1
            msg_out = f"[-] {fund.scheme_code}: {msg}"
            if tqdm:
                tqdm.write(msg_out)
            else:
                print(msg_out)

        time.sleep(1)  # polite throttle for AMFI

    print(f"  Done. {ok_count} OK, {fail_count} failed.")


# ── Main ──────────────────────────────────────────────────────────────────────

def separator(title: str):
    width = 60
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def main():
    parser = argparse.ArgumentParser(
        description="Full historical data load for Nivesh Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--nav-period",   default="max",
                        choices=["1y", "5y", "10y", "max"],
                        help="Benchmark NAV history window (default: max)")
    parser.add_argument("--price-period", default="5y",
                        choices=["1y", "2y", "3y", "5y", "10y", "max"],
                        help="Stock price history window (default: 5y)")
    parser.add_argument("--fund-period",  default="max",
                        choices=["1y", "3y", "5y", "max"],
                        help="Fund NAV history window (default: max)")
    parser.add_argument("--skip-master",  action="store_true",
                        help="Skip Phase 1 (master data + benchmark NAV)")
    parser.add_argument("--skip-nav",     action="store_true",
                        help="Skip Phase 2 (fund NAV history + metrics)")
    parser.add_argument("--skip-prices",  action="store_true",
                        help="Skip Phase 3 (stock price history)")
    parser.add_argument("--dry-run",      action="store_true",
                        help="Preview without writing to DB")
    parser.add_argument("--batch-size",   type=int, default=20,
                        help="Stocks per yfinance batch (default: 20)")
    args = parser.parse_args()

    start = time.time()

    print("\n" + "=" * 60)
    print("  Nivesh Platform — Historical Data Seed")
    print("=" * 60)
    if args.dry_run:
        print("  *** DRY RUN — no data will be written ***")

    # ── Phase 1: Master data + benchmark NAV ──────────────────────────────────
    if not args.skip_master:
        separator("Phase 1a — Benchmark master")
        seed_benchmarks.seed(dry_run=args.dry_run)

        separator("Phase 1b — Stock master")
        seed_stocks.seed(dry_run=args.dry_run)

        separator("Phase 1c — Fund master")
        seed_funds.seed(dry_run=args.dry_run)

        separator(f"Phase 1d — Benchmark NAV history  (period={args.nav_period})")
        seed_benchmark_nav.seed(dry_run=args.dry_run, period=args.nav_period)
    else:
        print("\n[skipped] Phase 1 — master data + benchmark NAV")

    # ── Phase 2: Fund NAV history + metrics ───────────────────────────────────
    if not args.skip_nav:
        separator(f"Phase 2 — Fund NAV history + metrics  (period={args.fund_period})")
        print("  This takes 30–60 minutes for all active funds.")
        run_fund_nav_sync(period=args.fund_period, dry_run=args.dry_run)
    else:
        print("\n[skipped] Phase 2 — fund NAV history")

    # ── Phase 3: Stock price history ──────────────────────────────────────────
    if not args.skip_prices:
        separator(f"Phase 3 — Stock price history  (period={args.price_period})")
        print("  This takes 20–40 minutes for ~500 stocks.")
        seed_stock_prices.seed(
            period=args.price_period,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
        )
    else:
        print("\n[skipped] Phase 3 — stock price history")

    elapsed = round(time.time() - start)
    separator(f"Complete  ({elapsed // 60} min {elapsed % 60} sec)")
    if args.dry_run:
        print("  DRY RUN — re-run without --dry-run to write data.")
    print()


if __name__ == "__main__":
    main()
