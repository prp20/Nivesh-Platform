"""
pipeline/technical_analysis.py — TA-Lib technical indicator computation.

Public interface (called by app/routers/pipeline.py):
    run_technical_analysis_all()            — compute indicators for all active stocks
    run_technical_analysis_one(symbol)      — compute for a single stock, returns dict
    get_ta_status()                         — list of {symbol, last_date, status} per stock

Indicators computed (all on daily timeframe):
    Trend:      SMA(20/50/200), EMA(9/21/50)
    Momentum:   RSI(14), MACD(12/26/9), Stochastic(14,3), ROC(14), CCI(20), Williams %R(14)
    Volatility: Bollinger Bands(20), ATR(14)
    Volume:     OBV, Volume SMA(20/50), Volume ratio, VWAP-20
    Strength:   ADX(14)
    Comparative: pct_from_52w_high, pct_from_52w_low

Note: Uses TA-Lib (talib), NOT pandas-ta.
      Processes one stock at a time — Render free tier is 512MB RAM.
"""

import asyncio
import gc
import logging
from datetime import date, timedelta
from typing import Optional

import numpy as np
from sqlalchemy import select, func as sa_func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Stock, PriceData, TechnicalIndicator
from app.crud import get_active_stocks, upsert_technical_indicators, start_etl_run, finish_etl_run

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 260   # ~1 year of trading days (enough for SMA200)
_TIMEFRAME = "1D"


# ── Public interface ─────────────────────────────────────────────────────────


async def run_technical_analysis_all() -> dict:
    """Compute technical indicators for all active non-index stocks."""
    async with AsyncSessionLocal() as db:
        run, created = await start_etl_run(db, pipeline_name="technical_analysis", triggered_by="scheduler")
        if not created:
            logger.warning("[technical_analysis] already RUNNING — skipping")
            return {"skipped": True}

        try:
            stocks = await get_active_stocks(db, is_index=False)
            succeeded = 0
            failed = 0
            for stock in stocks:
                try:
                    result = await _compute_for_stock(db, stock)
                    if result:
                        succeeded += 1
                except Exception as exc:
                    logger.warning(f"[ta] {stock.symbol} failed — {exc}")
                    failed += 1
                # Force GC between stocks to keep memory low on Render 512MB
                gc.collect()

            status = "COMPLETED" if failed == 0 else "PARTIAL"
            await finish_etl_run(
                db, run.id, status,
                records_out=succeeded,
                error_msg=f"{failed} stocks failed" if failed else None,
            )
            return {"succeeded": succeeded, "failed": failed}

        except Exception as exc:
            logger.exception("[technical_analysis] pipeline-level failure")
            await finish_etl_run(db, run.id, "FAILED", error_msg=str(exc)[:1000])
            raise


async def run_technical_analysis_one(symbol: str) -> Optional[dict]:
    """
    Compute technical indicators for a single stock by symbol.

    Returns the computed indicator dict for the latest date, or None if
    insufficient price data.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Stock).where(Stock.symbol == symbol, Stock.is_active.is_(True))
        )
        stock = result.scalar_one_or_none()
        if stock is None:
            raise ValueError(f"Active stock not found: {symbol}")
        return await _compute_for_stock(db, stock, return_latest=True)


async def get_ta_status() -> list:
    """
    Return per-stock TA status: last computed date + staleness flag.

    Status values:
        OK      — computed within the last 2 trading days
        STALE   — computed but older than 2 trading days
        MISSING — no indicator rows exist yet
    """
    async with AsyncSessionLocal() as db:
        stocks = await get_active_stocks(db, is_index=False)
        today = date.today()
        cutoff = today - timedelta(days=2)

        result = await db.execute(
            select(
                TechnicalIndicator.stock_id,
                sa_func.max(TechnicalIndicator.ind_date).label("last_date"),
            ).group_by(TechnicalIndicator.stock_id)
        )
        last_dates = {row.stock_id: row.last_date for row in result}

        statuses = []
        for stock in stocks:
            last = last_dates.get(stock.id)
            if last is None:
                status = "MISSING"
            elif last < cutoff:
                status = "STALE"
            else:
                status = "OK"
            statuses.append({"symbol": stock.symbol, "stock_id": stock.id, "last_date": last, "status": status})

        return statuses


# ── Core computation ─────────────────────────────────────────────────────────


async def _compute_for_stock(
    db: AsyncSession,
    stock,
    return_latest: bool = False,
) -> Optional[dict]:
    """
    Fetch price data, compute all indicators, upsert into technical_indicators.

    Returns the latest indicator dict if return_latest=True, else returns
    True on success / None if insufficient data.
    """
    from app.crud import get_price_data_for_ta

    rows = await get_price_data_for_ta(db, stock.id, lookback_days=_LOOKBACK_DAYS)
    if len(rows) < 50:
        logger.debug(f"[ta] {stock.symbol} — only {len(rows)} rows, need 50+ — skipping")
        return None

    # Build numpy arrays from PriceData ORM objects
    opens   = np.array([float(r.open)   if r.open   is not None else np.nan for r in rows], dtype=np.float64)
    highs   = np.array([float(r.high)   if r.high   is not None else np.nan for r in rows], dtype=np.float64)
    lows    = np.array([float(r.low)    if r.low    is not None else np.nan for r in rows], dtype=np.float64)
    closes  = np.array([float(r.close)  for r in rows], dtype=np.float64)
    volumes = np.array([int(r.volume)   if r.volume is not None else 0 for r in rows], dtype=np.float64)
    dates   = [r.price_date for r in rows]

    indicators = await asyncio.to_thread(_compute_talib, opens, highs, lows, closes, volumes)

    # Build upsert rows for every date that has at least the close price
    upsert_rows = []
    for i, d in enumerate(dates):
        row = {
            "stock_id":  stock.id,
            "ind_date":  d,
            "timeframe": _TIMEFRAME,
        }
        for key, arr in indicators.items():
            val = arr[i] if i < len(arr) else np.nan
            row[key] = None if (val is None or (isinstance(val, float) and np.isnan(val))) else val

        # 52-week high/low distance — computed from closes in the window
        window_start = max(0, i - 251)
        window = closes[window_start : i + 1]
        if len(window) > 0:
            w_high = float(np.nanmax(window))
            w_low  = float(np.nanmin(window))
            close_val = closes[i]
            row["pct_from_52w_high"] = round((close_val - w_high) / w_high * 100, 3) if w_high else None
            row["pct_from_52w_low"]  = round((close_val - w_low)  / w_low  * 100, 3) if w_low else None

        upsert_rows.append(row)

    await upsert_technical_indicators(db, upsert_rows)

    latest = upsert_rows[-1] if upsert_rows else None

    # Free memory immediately
    del opens, highs, lows, closes, volumes, indicators, upsert_rows
    gc.collect()

    if return_latest:
        return latest
    return True


def _compute_talib(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
) -> dict:
    """
    Compute all TA-Lib indicators.  Runs in a thread via asyncio.to_thread().
    Returns dict of {column_name: np.ndarray} aligned to the input arrays.
    """
    import talib

    n = len(closes)

    def _pad(arr: np.ndarray) -> np.ndarray:
        """Pad short arrays to length n with NaN."""
        out = np.full(n, np.nan)
        out[n - len(arr):] = arr
        return out

    sma_20  = _pad(talib.SMA(closes, timeperiod=20))
    sma_50  = _pad(talib.SMA(closes, timeperiod=50))
    sma_200 = _pad(talib.SMA(closes, timeperiod=200))
    ema_9   = _pad(talib.EMA(closes, timeperiod=9))
    ema_21  = _pad(talib.EMA(closes, timeperiod=21))
    ema_50  = _pad(talib.EMA(closes, timeperiod=50))

    rsi_14 = _pad(talib.RSI(closes, timeperiod=14))

    macd_line_arr, macd_sig_arr, macd_hist_arr = talib.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)
    macd_line   = _pad(macd_line_arr)
    macd_signal = _pad(macd_sig_arr)
    macd_hist   = _pad(macd_hist_arr)

    bb_upper_arr, bb_mid_arr, bb_lower_arr = talib.BBANDS(closes, timeperiod=20)
    bb_upper  = _pad(bb_upper_arr)
    bb_middle = _pad(bb_mid_arr)
    bb_lower  = _pad(bb_lower_arr)

    atr_14 = _pad(talib.ATR(highs, lows, closes, timeperiod=14))
    adx_14 = _pad(talib.ADX(highs, lows, closes, timeperiod=14))

    stoch_k_arr, stoch_d_arr = talib.STOCH(highs, lows, closes, fastk_period=14, slowk_period=3, slowd_period=3)
    stoch_k = _pad(stoch_k_arr)
    stoch_d = _pad(stoch_d_arr)

    obv = _pad(talib.OBV(closes, volumes))
    cci_20    = _pad(talib.CCI(highs, lows, closes, timeperiod=20))
    williams_r = _pad(talib.WILLR(highs, lows, closes, timeperiod=14))
    roc_14    = _pad(talib.ROC(closes, timeperiod=14))

    # Volume SMAs and ratio
    vol_sma_20 = _pad(talib.SMA(volumes, timeperiod=20))
    vol_sma_50 = _pad(talib.SMA(volumes, timeperiod=50))
    vol_ratio = np.where(
        (vol_sma_20 > 0) & ~np.isnan(vol_sma_20),
        volumes / vol_sma_20,
        np.nan,
    )

    # VWAP-20: cumulative(typical_price * volume) / cumulative(volume) over 20 days
    typical = (highs + lows + closes) / 3.0
    vwap_20 = np.full(n, np.nan)
    for i in range(19, n):
        w = typical[i - 19: i + 1]
        v = volumes[i - 19: i + 1]
        total_vol = v.sum()
        vwap_20[i] = (w * v).sum() / total_vol if total_vol > 0 else np.nan

    return {
        "sma_20":        sma_20,
        "sma_50":        sma_50,
        "sma_200":       sma_200,
        "ema_9":         ema_9,
        "ema_21":        ema_21,
        "ema_50":        ema_50,
        "rsi_14":        rsi_14,
        "macd_line":     macd_line,
        "macd_signal":   macd_signal,
        "macd_hist":     macd_hist,
        "bb_upper":      bb_upper,
        "bb_middle":     bb_middle,
        "bb_lower":      bb_lower,
        "atr_14":        atr_14,
        "adx_14":        adx_14,
        "stoch_k":       stoch_k,
        "stoch_d":       stoch_d,
        "obv":           obv,
        "cci_20":        cci_20,
        "williams_r":    williams_r,
        "roc_14":        roc_14,
        "volume_sma_20": vol_sma_20,
        "volume_sma_50": vol_sma_50,
        "volume_ratio":  vol_ratio,
        "vwap_20":       vwap_20,
    }
