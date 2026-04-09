"""
backend/pipeline/technical_analysis.py

Computes technical indicators from price_data using TA-Lib and
stores results in the technical_indicators table.

Entry points:
  run_technical_analysis_all()    — all active stocks (scheduler / background task)
  run_technical_analysis_one(symbol) — single stock (HTTP trigger)
"""

import logging
import numpy as np
import pandas as pd
import talib
from datetime import date
from typing import Optional

from pipeline.audit import audit_job
from app.database import raw_connection

logger = logging.getLogger(__name__)

TIMEFRAME = "1d"
MIN_ROWS_REQUIRED = 200  # need 200 rows for SMA-200; shorter series get NaN


# ─── Main entry points ────────────────────────────────────────────────────────

async def run_technical_analysis_all() -> dict:
    """Compute TA indicators for all active non-index stocks. For scheduler."""
    async with audit_job("technical_analysis_all") as audit:
        stocks = await _fetch_active_stocks()
        success, failed = 0, 0
        for stock in stocks:
            try:
                await _compute_and_store(stock["id"], stock["symbol"])
                success += 1
            except Exception as e:
                logger.error(f"TA failed for {stock['symbol']}: {e}")
                failed += 1
        audit.records_out = success
        logger.info(f"technical_analysis_all: {success} ok, {failed} failed")
        return {"stocks_processed": success, "stocks_failed": failed}


async def run_technical_analysis_one(symbol: str) -> dict:
    """Compute TA indicators for a single stock. Returns computed values."""
    async with audit_job("technical_analysis_single") as audit:
        stock = await _fetch_stock_by_symbol(symbol)
        if not stock:
            raise ValueError(f"Stock '{symbol}' not found or inactive")
        row = await _compute_and_store(stock["id"], stock["symbol"])
        audit.records_out = 1 if row else 0
        return row or {}


# ─── Core computation ─────────────────────────────────────────────────────────

async def _compute_and_store(stock_id: int, symbol: str) -> Optional[dict]:
    """Fetch price history, compute all indicators, upsert the latest row."""
    prices = await _fetch_price_history(stock_id)
    if len(prices) < 20:
        logger.warning(f"{symbol}: only {len(prices)} rows — need ≥20 for basic indicators")
        return None

    df = pd.DataFrame(prices, columns=["price_date", "open", "high", "low", "close", "volume"])
    df = df.sort_values("price_date").reset_index(drop=True)

    # Convert to float64 numpy arrays (TA-Lib requirement)
    op    = df["open"].astype(float).to_numpy()
    hi    = df["high"].astype(float).to_numpy()
    lo    = df["low"].astype(float).to_numpy()
    cl    = df["close"].astype(float).to_numpy()
    vol   = df["volume"].astype(float).to_numpy()

    def last(arr):
        """Return last non-NaN value or None."""
        arr = np.array(arr, dtype=float)
        valid = arr[~np.isnan(arr)]
        return float(valid[-1]) if len(valid) > 0 else None

    def last_int(arr):
        v = last(arr)
        return int(v) if v is not None else None

    # ── Moving Averages ───────────────────────────────────────────────────────
    sma_20  = last(talib.SMA(cl, timeperiod=20))
    sma_50  = last(talib.SMA(cl, timeperiod=50))
    sma_200 = last(talib.SMA(cl, timeperiod=200)) if len(cl) >= 200 else None

    ema_9   = last(talib.EMA(cl, timeperiod=9))
    ema_21  = last(talib.EMA(cl, timeperiod=21))
    ema_50  = last(talib.EMA(cl, timeperiod=50))

    # ── RSI ───────────────────────────────────────────────────────────────────
    rsi_14  = last(talib.RSI(cl, timeperiod=14))

    # ── MACD(12,26,9) ─────────────────────────────────────────────────────────
    macd_line, macd_signal, macd_hist = talib.MACD(cl, fastperiod=12, slowperiod=26, signalperiod=9)
    macd_line   = last(macd_line)
    macd_signal = last(macd_signal)
    macd_hist   = last(macd_hist)

    # ── Bollinger Bands (20, 2σ) ──────────────────────────────────────────────
    bb_upper, bb_middle, bb_lower = talib.BBANDS(cl, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    bb_upper  = last(bb_upper)
    bb_middle = last(bb_middle)
    bb_lower  = last(bb_lower)

    # ── ATR(14) ───────────────────────────────────────────────────────────────
    atr_14 = last(talib.ATR(hi, lo, cl, timeperiod=14))

    # ── ADX(14) ───────────────────────────────────────────────────────────────
    adx_14 = last(talib.ADX(hi, lo, cl, timeperiod=14))

    # ── Stochastic(14,3) ──────────────────────────────────────────────────────
    stoch_k, stoch_d = talib.STOCH(hi, lo, cl, fastk_period=14, slowk_period=3, slowd_period=3)
    stoch_k = last(stoch_k)
    stoch_d = last(stoch_d)

    # ── Volume SMA(20) ────────────────────────────────────────────────────────
    volume_sma_20 = last_int(talib.SMA(vol, timeperiod=20))

    ind_date = df["price_date"].iloc[-1]
    if hasattr(ind_date, "date"):
        ind_date = ind_date.date()

    row = {
        "stock_id":     stock_id,
        "ind_date":     ind_date,
        "timeframe":    TIMEFRAME,
        "sma_20":       sma_20,
        "sma_50":       sma_50,
        "sma_200":      sma_200,
        "ema_9":        ema_9,
        "ema_21":       ema_21,
        "ema_50":       ema_50,
        "rsi_14":       rsi_14,
        "macd_line":    macd_line,
        "macd_signal":  macd_signal,
        "macd_hist":    macd_hist,
        "bb_upper":     bb_upper,
        "bb_middle":    bb_middle,
        "bb_lower":     bb_lower,
        "atr_14":       atr_14,
        "adx_14":       adx_14,
        "stoch_k":      stoch_k,
        "stoch_d":      stoch_d,
        "volume_sma_20": volume_sma_20,
    }

    await _upsert_indicators(row)
    logger.debug(f"{symbol}: TA upserted for {ind_date}")
    return row


# ─── DB helpers ───────────────────────────────────────────────────────────────

async def _fetch_active_stocks() -> list:
    sql = """
        SELECT id, symbol FROM stocks
        WHERE is_active = TRUE AND is_index = FALSE
        ORDER BY id
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql)
        return [dict(r) for r in rows]


async def _fetch_stock_by_symbol(symbol: str) -> Optional[dict]:
    async with raw_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id, symbol FROM stocks WHERE symbol=$1 AND is_active=TRUE",
            symbol.upper()
        )
        return dict(row) if row else None


async def _fetch_price_history(stock_id: int) -> list:
    """Fetch all OHLCV rows ordered chronologically."""
    sql = """
        SELECT price_date, open, high, low, close, volume
        FROM price_data
        WHERE stock_id = $1
        ORDER BY price_date ASC
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql, stock_id)
        return [tuple(r) for r in rows]


async def _upsert_indicators(row: dict):
    sql = """
        INSERT INTO technical_indicators
            (stock_id, ind_date, timeframe,
             sma_20, sma_50, sma_200,
             ema_9, ema_21, ema_50,
             rsi_14,
             macd_line, macd_signal, macd_hist,
             bb_upper, bb_middle, bb_lower,
             atr_14, adx_14,
             stoch_k, stoch_d,
             volume_sma_20)
        VALUES
            ($1,$2,$3, $4,$5,$6, $7,$8,$9, $10, $11,$12,$13, $14,$15,$16, $17,$18, $19,$20, $21)
        ON CONFLICT (stock_id, ind_date, timeframe) DO UPDATE SET
            sma_20=$4, sma_50=$5, sma_200=$6,
            ema_9=$7, ema_21=$8, ema_50=$9,
            rsi_14=$10,
            macd_line=$11, macd_signal=$12, macd_hist=$13,
            bb_upper=$14, bb_middle=$15, bb_lower=$16,
            atr_14=$17, adx_14=$18,
            stoch_k=$19, stoch_d=$20,
            volume_sma_20=$21
    """
    r = row
    async with raw_connection() as conn:
        await conn.execute(
            sql,
            r["stock_id"], r["ind_date"], r["timeframe"],
            r["sma_20"],   r["sma_50"],   r["sma_200"],
            r["ema_9"],    r["ema_21"],   r["ema_50"],
            r["rsi_14"],
            r["macd_line"], r["macd_signal"], r["macd_hist"],
            r["bb_upper"],  r["bb_middle"],   r["bb_lower"],
            r["atr_14"],    r["adx_14"],
            r["stoch_k"],   r["stoch_d"],
            r["volume_sma_20"],
        )


async def get_ta_status() -> list:
    """Return last TA date per stock and flag stale ones (>2 days old)."""
    sql = """
        SELECT
            s.symbol,
            s.company_name,
            MAX(ti.ind_date) AS last_ta_date,
            CASE
                WHEN MAX(ti.ind_date) IS NULL THEN 'MISSING'
                WHEN MAX(ti.ind_date) < CURRENT_DATE - INTERVAL '2 days' THEN 'STALE'
                ELSE 'OK'
            END AS status
        FROM stocks s
        LEFT JOIN technical_indicators ti ON ti.stock_id = s.id AND ti.timeframe = '1d'
        WHERE s.is_active = TRUE AND s.is_index = FALSE
        GROUP BY s.id, s.symbol, s.company_name
        ORDER BY last_ta_date ASC NULLS FIRST
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql)
        return [dict(r) for r in rows]
