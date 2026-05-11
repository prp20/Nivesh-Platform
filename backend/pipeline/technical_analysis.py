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
from app.db_compat import raw_connection, db_execute, db_fetch, db_fetchrow

logger = logging.getLogger(__name__)

TIMEFRAME = "1d"
MIN_ROWS_REQUIRED = 200  # need 200 rows for SMA-200; shorter series get NaN


# ─── Main entry points ────────────────────────────────────────────────────────

async def run_technical_analysis_all() -> dict:
    """Compute TA indicators for all active non-index stocks. For scheduler."""
    stocks = await _fetch_active_stocks()
    async with audit_job("technical_analysis_all", records_in=len(stocks)) as audit:
        # Fetch benchmark data once for the batch
        nifty_history = await _fetch_benchmark_history()
        
        success, failed = 0, 0
        for i, stock in enumerate(stocks):
            try:
                await _compute_and_store(stock["id"], stock["symbol"], nifty_history)
                success += 1
            except Exception as e:
                logger.error(f"TA failed for {stock['symbol']}: {e}")
                failed += 1
            
            # Report progress after each stock
            await audit.update_progress(i + 1)
            
        audit.records_out = success
        logger.info(f"technical_analysis_all: {success} ok, {failed} failed")
        return {"stocks_processed": success, "stocks_failed": failed}


async def run_technical_analysis_one(symbol: str) -> dict:
    """Compute TA indicators for a single stock. Returns computed values."""
    async with audit_job("technical_analysis_single") as audit:
        stock = await _fetch_stock_by_symbol(symbol)
        if not stock:
            raise ValueError(f"Stock '{symbol}' not found or inactive")
        
        # Need benchmark data for relative metrics
        nifty_history = await _fetch_benchmark_history()
        
        row = await _compute_and_store(stock["id"], stock["symbol"], nifty_history)
        audit.records_out = 1 if row else 0
        return row or {}


# ─── Core computation ─────────────────────────────────────────────────────────

async def _compute_and_store(stock_id: int, symbol: str, nifty_history: list = None) -> Optional[dict]:
    """Fetch price history, compute all indicators, upsert the latest row."""
    prices = await _fetch_price_history(stock_id)
    if len(prices) < 20:
        logger.warning(f"{symbol}: only {len(prices)} rows — need ≥20 for basic indicators")
        return None

    df = pd.DataFrame(prices, columns=["price_date", "open", "high", "low", "close", "volume"])
    df = df.sort_values("price_date").reset_index(drop=True)

    # Convert to float64 numpy arrays (TA-Lib requirement)
    # op    = df["open"].astype(float).to_numpy()
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

    # ── Volume Indicators ─────────────────────────────────────────────────────
    volume_sma_20 = last_int(talib.SMA(vol, timeperiod=20))
    volume_sma_50 = last_int(talib.SMA(vol, timeperiod=50))
    volume_ratio  = float(vol[-1] / volume_sma_50) if vol[-1] and volume_sma_50 else None
    obv           = last_int(talib.OBV(cl, vol))

    # ── Advanced Indicators ───────────────────────────────────────────────────
    cci_20     = last(talib.CCI(hi, lo, cl, timeperiod=20))
    williams_r = last(talib.WILLR(hi, lo, cl, timeperiod=14))
    roc_14     = last(talib.ROC(cl, timeperiod=14))
    
    # VWAP (approximate: cumulative Σ(P*V)/ΣV)
    cum_vol = np.cumsum(vol)
    vwap_all = np.where(cum_vol > 0, np.cumsum(cl * vol) / cum_vol, cl)
    vwap_20  = vwap_all[-1] if len(vwap_all) > 0 else None

    # ── Relative Metrics (vs Nifty) ───────────────────────────────────────────
    beta_1y = None
    rs_6m   = None
    if nifty_history:
        nifty_df = pd.DataFrame(nifty_history, columns=["price_date", "nifty_close"])
        merged = pd.merge(df[["price_date", "close"]], nifty_df, on="price_date", how="inner")
        if len(merged) > 20:
            merged["s_ret"] = merged["close"].pct_change()
            merged["n_ret"] = merged["nifty_close"].pct_change()
            
            # Beta (rolling 1Y = 252 days)
            win = 252 if len(merged) >= 252 else len(merged)
            rolling = merged.iloc[-win:]
            if len(rolling) > 100:
                cov = rolling["s_ret"].cov(rolling["n_ret"])
                var = rolling["n_ret"].var()
                beta_1y = float(cov / var) if var > 0 else None
            
            # RS (6M vs Nifty) - simple alpha
            lb = 126 if len(merged) >= 126 else len(merged)
            merged_lb = merged.iloc[-lb:].copy()
            if len(merged_lb) > 20:
                try:
                    s_first = float(merged_lb["close"].iloc[0])
                    s_last = float(merged_lb["close"].iloc[-1])
                    n_first = float(merged_lb["nifty_close"].iloc[0])
                    n_last = float(merged_lb["nifty_close"].iloc[-1])
                    
                    if s_first > 0 and n_first > 0:
                        s_p = (s_last / s_first) - 1
                        n_p = (n_last / n_first) - 1
                        val = float(s_p - n_p) * 100
                        import math
                        if not math.isnan(val) and not math.isinf(val):
                            rs_6m = val
                except Exception as e:
                    logger.warning(f"Error computing RS for {symbol}: {e}")

    # ── 52-Week Position ──────────────────────────────────────────────────────
    win_52w = 252 if len(cl) >= 252 else len(cl)
    hi_52w  = np.max(hi[-win_52w:]) if len(hi) > 0 else None
    lo_52w  = np.min(lo[-win_52w:]) if len(lo) > 0 else None
    pct_f_hi = float((cl[-1] - hi_52w) / hi_52w * 100) if cl[-1] and hi_52w else None
    pct_f_lo = float((cl[-1] - lo_52w) / lo_52w * 100) if cl[-1] and lo_52w else None

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
        "volume_sma_50": volume_sma_50,
        "volume_ratio":  volume_ratio,
        "obv":           obv,
        "vwap_20":       vwap_20,
        "cci_20":        cci_20,
        "williams_r":    williams_r,
        "roc_14":        roc_14,
        "beta_1y":       beta_1y,
        "rs_6m_vs_nifty": rs_6m,
        "pct_from_52w_high": pct_f_hi,
        "pct_from_52w_low":  pct_f_lo,
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
        rows = await db_fetch(conn, sql)
        return [dict(r) for r in rows]


async def _fetch_stock_by_symbol(symbol: str) -> Optional[dict]:
    async with raw_connection() as conn:
        row = await db_fetchrow(conn,
            "SELECT id, symbol FROM stocks WHERE symbol=$1 AND is_active=TRUE",
            (symbol.upper(),)
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
        rows = await db_fetch(conn, sql, (stock_id,))
        return [tuple(r.values()) for r in rows]


async def _fetch_benchmark_history() -> list:
    """Fetch Nifty 50 history for relative metrics."""
    sql = """
        SELECT nav_date as price_date, index_value as close
        FROM benchmark_nav_history
        WHERE benchmark_code = 'NIFTY50'
        ORDER BY nav_date ASC
    """
    async with raw_connection() as conn:
        rows = await db_fetch(conn, sql)
        return [dict(r) for r in rows]


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
             volume_sma_20, volume_sma_50, volume_ratio,
             obv, vwap_20, cci_20, williams_r, roc_14,
             beta_1y, rs_6m_vs_nifty, 
             pct_from_52w_high, pct_from_52w_low)
        VALUES
            ($1,$2,$3, $4,$5,$6, $7,$8,$9, $10, $11,$12,$13, $14,$15,$16, $17,$18, $19,$20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32)
        ON CONFLICT (stock_id, ind_date, timeframe) DO UPDATE SET
            sma_20=$4, sma_50=$5, sma_200=$6,
            ema_9=$7, ema_21=$8, ema_50=$9,
            rsi_14=$10,
            macd_line=$11, macd_signal=$12, macd_hist=$13,
            bb_upper=$14, bb_middle=$15, bb_lower=$16,
            atr_14=$17, adx_14=$18,
            stoch_k=$19, stoch_d=$20,
            volume_sma_20=$21, volume_sma_50=$22, volume_ratio=$23,
            obv=$24, vwap_20=$25, cci_20=$26, williams_r=$27, roc_14=$28,
            beta_1y=$29, rs_6m_vs_nifty=$30, 
            pct_from_52w_high=$31, pct_from_52w_low=$32
    """
    r = row
    async with raw_connection() as conn:
        await db_execute(conn, sql, (
            r["stock_id"], r["ind_date"], r["timeframe"],
            r["sma_20"],   r["sma_50"],   r["sma_200"],
            r["ema_9"],    r["ema_21"],   r["ema_50"],
            r["rsi_14"],
            r["macd_line"], r["macd_signal"], r["macd_hist"],
            r["bb_upper"],  r["bb_middle"],   r["bb_lower"],
            r["atr_14"],    r["adx_14"],
            r["stoch_k"],   r["stoch_d"],
            r["volume_sma_20"], r["volume_sma_50"], r["volume_ratio"],
            r["obv"],       r["vwap_20"],     r["cci_20"],      r["williams_r"],  r["roc_14"],
            r["beta_1y"],   r["rs_6m_vs_nifty"],
            r["pct_from_52w_high"], r["pct_from_52w_low"],
        ))


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
        rows = await db_fetch(conn, sql)
        return [dict(r) for r in rows]
