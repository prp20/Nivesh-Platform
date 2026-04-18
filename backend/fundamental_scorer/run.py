import asyncio
import argparse
import sys
import os

# Ensure the parent directory is in the path so we can import 'app' and 'fundamental_scorer'
# This allows running from the backend directory: python -m fundamental_scorer.run --symbol RELIANCE --id 123
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from fundamental_scorer.graph import run_fundamental_scorer

async def main():
    """
    CLI entry point to manually trigger fundamental scoring for a specific stock.
    Usage: python -m fundamental_scorer.run --symbol SYMBOL --id ID
    """
    parser = argparse.ArgumentParser(description="Run Fundamental Scorer for a stock manually.")
    parser.add_argument("--symbol", required=True, help="The stock symbol (e.g., RELIANCE)")
    parser.add_argument("--id", type=int, required=True, help="The numeric stock_id in the database")
    parser.add_argument("--version", default="v1.0", help="Score version tag (default: v1.0)")
    parser.add_argument("--period", default="annual", choices=["annual", "quarterly"], help="Period type")
    
    args = parser.parse_args()
    
    async with AsyncSessionLocal() as db:
        print(f"\n[Scorer] Initializing workflow for {args.symbol} (ID: {args.id})...")
        
        result = await run_fundamental_scorer(
            stock_id=args.id, 
            symbol=args.symbol, 
            db=db,
            period_type=args.period,
            score_version=args.version
        )
        
        print("-" * 50)
        if result.get("status") == "COMPLETED":
            print(f"✅ SUCCESS: {args.symbol} scoring completed.")
            print(f"📊 Composite Score: {result.get('composite_score')}/10")
            print(f"🏷️  Label: {result.get('reasoning_label')}")
            print(f"📝 Summary: {result.get('reasoning_text')[:100]}...")
            
            print("\nComponents:")
            print(f"  - P&L: {result['pl_results'].get('score')}")
            print(f"  - BS:  {result['bs_results'].get('score')}")
            print(f"  - CF:  {result['cf_results'].get('score')}")
        else:
            print(f"❌ FAILED: {result.get('error')}")
            print("\nExecution Logs:")
            for log in result.get("logs", []):
                print(f"  - {log}")
        print("-" * 50 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
