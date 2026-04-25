import asyncio
from app.database import raw_connection

async def dump_audit():
    async with raw_connection() as conn:
        rows = await conn.fetch("""
            SELECT job_name, stock_id, started_at, ended_at, status, error_msg, records_in, records_out
            FROM pipeline_audit
            ORDER BY started_at DESC
            LIMIT 20
        """)
        print(f"{'Job Name':<30} | {'SID':<4} | {'Status':<10} | {'Rec Out':<8} | {'Error'}")
        print("-" * 110)
        for r in rows:
            print(f"{r['job_name']:<30} | {str(r['stock_id']):<4} | {r['status']:<10} | {str(r['records_out']):<8} | {r['error_msg']}")

if __name__ == "__main__":
    asyncio.run(dump_audit())
