from typing import List
import io
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from .. import crud, schemas

router = APIRouter(prefix="/benchmark-navs", tags=["benchmark-navs"])

@router.post("/{benchmark_code}/bulk", status_code=201)
async def upload_bulk_benchmark_nav(benchmark_code: str, payload: schemas.BulkNavUpload, session: AsyncSession = Depends(get_db)):
    count = await crud.bulk_insert_benchmark_navs(session, benchmark_code, payload.data)
    return {"message": f"Successfully processed {count} benchmark records"}

@router.post("/{benchmark_code}/upload", status_code=201)
async def upload_benchmark_csv(
    benchmark_code: str, 
    file: UploadFile = File(...), 
    session: AsyncSession = Depends(get_db)
):
    # Check if benchmark exists
    benchmark = await crud.get_benchmark_master(session, benchmark_code)
    if not benchmark:
        raise HTTPException(status_code=404, detail=f"Benchmark {benchmark_code} not found")

    try:
        content = await file.read()
        # Nifty CSVs are often comma separated with quotes
        df = pd.read_csv(io.BytesIO(content))
        
        # Standardize columns (strip quotes and spaces if any)
        df.columns = [c.strip().replace('"', '') for c in df.columns]
        
        required = ["Date", "Close"]
        if not all(c in df.columns for c in required):
            raise HTTPException(
                status_code=400, 
                detail=f"CSV must contain 'Date' and 'Close' columns. Found: {list(df.columns)}"
            )

        nav_data = {}
        for _, row in df.iterrows():
            try:
                # pandas handles "20 Feb 2009" and other common formats automatically
                dt = pd.to_datetime(row["Date"])
                date_str = dt.strftime("%Y-%m-%d")
                val = float(str(row["Close"]).replace(',', '')) # Handle comma in numbers
                nav_data[date_str] = val
            except Exception as row_err:
                print(f"Skipping row due to error: {row_err}")
                continue

        if not nav_data:
            raise HTTPException(status_code=400, detail="No valid data found in CSV")

        count = await crud.bulk_insert_benchmark_navs(session, benchmark_code, nav_data)
        return {
            "message": f"Successfully processed {count} records for {benchmark_code}",
            "count": count
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process CSV: {str(e)}")

@router.get("/{benchmark_code}", response_model=List[schemas.BenchmarkNavHistoryRead])
async def get_benchmark_nav_history(benchmark_code: str, limit: int = 100, session: AsyncSession = Depends(get_db)):
    return await crud.get_benchmark_nav_history(session, benchmark_code, limit)
