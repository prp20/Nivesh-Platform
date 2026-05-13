"""
run_all_seeds.py — Runs all seed scripts in dependency order.

Order:
  1. seed_benchmarks (benchmark_master)
  2. seed_stocks     (stocks — equities + indices)
  3. seed_funds      (fund_master)

Prerequisites:
  - Alembic migrations must have been applied first: `alembic upgrade head`
  - DATABASE_URL must be set (Supavisor pooler URL, port 6543)

Usage:
  export DATABASE_URL="postgresql://postgres.[ref]:[pwd]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
  python scripts/seed/run_all_seeds.py [--dry-run]
"""
import sys
import argparse

# Import individual seed modules
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import seed_benchmarks
import seed_stocks
import seed_funds


def main():
    parser = argparse.ArgumentParser(description="Run all Phase 1 seed scripts")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    print("\n" + "="*50)
    print("Nivesh Platform — Phase 1 Data Seeding")
    print("="*50)

    print("\n[1/3] Benchmarks")
    seed_benchmarks.seed(dry_run=args.dry_run)

    print("\n[2/3] Stocks & Indices")
    seed_stocks.seed(dry_run=args.dry_run)

    print("\n[3/3] Mutual Funds")
    seed_funds.seed(dry_run=args.dry_run)

    print("\n" + "="*50)
    if args.dry_run:
        print("DRY RUN complete — no data written.")
    else:
        print("Seeding complete.")
    print("="*50 + "\n")


if __name__ == "__main__":
    main()
