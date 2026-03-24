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
        # All logic now uses the df loaded at line 30
        from .. import analytics
        from datetime import datetime
        
        # Determine CSV structure and safety check 'Index Name' if present
        if "Index Name" in df.columns:
            if not df.empty:
                raw_name = str(df.iloc[0]["Index Name"])
                # Normalize: strip, uppercase, then replace spaces / dashes / colons → underscore
                normalized_name = (
                    raw_name.strip().upper()
                    .replace(" ", "_")
                    .replace("-", "_")
                    .replace(":", "_")
                )
                # Alias map: CSV 'Index Name' variants → DB benchmark_code
                CSV_ALIAS_MAP = {
                    "NIFTY500_MULTICAP_50_25_25": "NIFTY500_MULTICAP_50_25_25",
                }
                normalized_name = CSV_ALIAS_MAP.get(normalized_name, normalized_name)

                if normalized_name != benchmark_code and not normalized_name.startswith(benchmark_code):
                    raise HTTPException(status_code=400, detail=f"CSV Index Name '{raw_name}' (normalized: {normalized_name}) does not map to target benchmark '{benchmark_code}'")

        # Process standard format: "Date","Close" vs specific format: "Index Name","Date","Open","High","Low","Close"
        if "Close" in df.columns and "Date" in df.columns:
            df = df[['Date', 'Close']].rename(columns={'Date': 'Date', 'Close': 'Value'})
        elif "Value" in df.columns and "Date" in df.columns:
            pass # already standard
        else:
            raise HTTPException(status_code=400, detail="CSV must contain 'Date' and either 'Close' or 'Value' columns")
            
        nav_dict = {
            pd.to_datetime(row['Date'], origin='unix').strftime('%Y-%m-%d') if isinstance(row['Date'], (int, float)) else pd.to_datetime(row['Date']).strftime('%Y-%m-%d'): float(row['Value'])
            for _, row in df.iterrows() if pd.notna(row['Value'])
        }
        
        records_inserted = await crud.bulk_insert_benchmark_navs(session, benchmark_code, nav_dict)
        
        # Triger Analytics Post Processing
        nav_history = await crud.get_benchmark_nav_history(session, benchmark_code, limit=2000)
        if nav_history:
            nav_list = [{"nav_date": n.nav_date, "nav_value": float(n.index_value)} for n in nav_history]
            calc_results = analytics.compute_all_metrics(nav_list, None)
            
            metrics_payload = {
                "benchmark_code": benchmark_code,
                "current_nav": calc_results["current_nav"],
                "nav_date": calc_results["nav_date"],
                "rolling_return_3year": calc_results.get("rolling_return_3year"),
                "rolling_return_5year": calc_results.get("rolling_return_5year"),
                "sharpe_ratio": calc_results.get("sharpe"),
                "sortino_ratio": calc_results.get("sortino"),
                "standard_deviation": calc_results.get("std_dev"),
                "maximum_drawdown": calc_results.get("max_drawdown"),
                "metrics_calculated_at": datetime.now()
            }
            await crud.upsert_benchmark_metrics(session, metrics_payload)

        return {"message": "Data uploaded successfully and metrics computed", "records_inserted": records_inserted}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process CSV: {str(e)}")

@router.get("/{benchmark_code}", response_model=List[schemas.BenchmarkNavHistoryRead])
async def get_benchmark_nav_history(benchmark_code: str, limit: int = 100, session: AsyncSession = Depends(get_db)):
    return await crud.get_benchmark_nav_history(session, benchmark_code, limit)
