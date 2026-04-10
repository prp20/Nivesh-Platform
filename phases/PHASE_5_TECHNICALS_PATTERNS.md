# Phase 5 — Technical Indicators & Pattern Engine
> **Duration:** Weeks 10–11  
> **Goal:** Compute and store all 15+ technical indicators using pandas-ta, detect 6 chart patterns using scipy, expose via API, implement candlestick chart in frontend.

---

## Prerequisites
- Phase 2 complete — `price_data` populated with 5 years of OHLCV
- `pandas-ta` and `scipy` installed

---

## 5.1 Technical Engine

Create `backend/pipeline/technical_engine.py`:

```python
# backend/pipeline/technical_engine.py
"""
Computes technical indicators for all active stocks using pandas-ta.
Only the most recent row is upserted on each run — history builds incrementally.
Requires at least 50 rows of price data (200 rows recommended for SMA-200).
"""

import logging
import pandas as pd
import pandas_ta as ta
from typing import Optional
from pipeline.audit import audit_job
from app.database import raw_connection

logger = logging.getLogger(__name__)
TIMEFRAMES = ["1d"]  # extend to "1w", "1mo" in later iteration


# ─── Main entry points ────────────────────────────────────────────────────────

async def run_technical_indicators():
    """Compute indicators for all active non-index stocks."""
    async with audit_job("technical_indicator_compute") as audit:
        stocks = await _fetch_active_stocks()
        total = 0
        for stock in stocks:
            for tf in TIMEFRAMES:
                try:
                    await compute_indicators_for_stock(stock["id"], tf)
                    total += 1
                except Exception as e:
                    logger.error(f"Indicator compute failed for {stock['symbol']} tf={tf}: {e}")
        audit.records_out = total


async def compute_indicators_for_stock(stock_id: int, timeframe: str = "1d"):
    """Compute and upsert indicators for one stock and timeframe."""
    df = await _fetch_price_df(stock_id, limit=300, timeframe=timeframe)
    if df is None or len(df) < 50:
        logger.debug(f"stock_id={stock_id}: insufficient data ({len(df) if df is not None else 0} rows)")
        return

    # ─── Compute all indicators ────────────────────────────────────────────────
    df.ta.sma(length=20,  append=True)
    df.ta.sma(length=50,  append=True)
    df.ta.sma(length=200, append=True)
    df.ta.ema(length=9,   append=True)
    df.ta.ema(length=21,  append=True)
    df.ta.ema(length=50,  append=True)
    df.ta.rsi(length=14,  append=True)
    df.ta.macd(append=True)               # MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
    df.ta.bbands(length=20, append=True)  # BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
    df.ta.atr(length=14,  append=True)    # ATRr_14
    df.ta.adx(length=14,  append=True)    # ADX_14
    df.ta.stoch(append=True)              # STOCHk_14_3_3, STOCHd_14_3_3
    df["VOL_SMA_20"] = df["volume"].rolling(20).mean()

    latest     = df.iloc[-1]
    latest_date = df.index[-1].date() if hasattr(df.index[-1], "date") else df.index[-1]

    row_data = {
        "sma_20":       _s(latest, "SMA_20"),
        "sma_50":       _s(latest, "SMA_50"),
        "sma_200":      _s(latest, "SMA_200"),
        "ema_9":        _s(latest, "EMA_9"),
        "ema_21":       _s(latest, "EMA_21"),
        "ema_50":       _s(latest, "EMA_50"),
        "rsi_14":       _s(latest, "RSI_14"),
        "macd_line":    _s(latest, "MACD_12_26_9"),
        "macd_signal":  _s(latest, "MACDs_12_26_9"),
        "macd_hist":    _s(latest, "MACDh_12_26_9"),
        "bb_upper":     _s(latest, "BBU_20_2.0"),
        "bb_middle":    _s(latest, "BBM_20_2.0"),
        "bb_lower":     _s(latest, "BBL_20_2.0"),
        "atr_14":       _s(latest, "ATRr_14"),
        "adx_14":       _s(latest, "ADX_14"),
        "stoch_k":      _s(latest, "STOCHk_14_3_3"),
        "stoch_d":      _s(latest, "STOCHd_14_3_3"),
        "volume_sma_20":int(_s(latest, "VOL_SMA_20") or 0),
    }

    await _upsert_indicators(stock_id, timeframe, latest_date, row_data)


# ─── Interpretation helpers (used by API) ─────────────────────────────────────

def interpret_signals(ti: dict, close: float) -> dict:
    """
    Returns human-readable signal labels from raw indicator values.
    Used in GET /stocks/{symbol}/technicals response.
    """
    signals = {}

    # RSI interpretation
    rsi = ti.get("rsi_14")
    if rsi is not None:
        if rsi >= 70:   signals["rsi"] = "OVERBOUGHT"
        elif rsi <= 30: signals["rsi"] = "OVERSOLD"
        elif rsi >= 55: signals["rsi"] = "BULLISH_ZONE"
        else:           signals["rsi"] = "NEUTRAL"

    # MACD interpretation
    macd_hist = ti.get("macd_hist")
    if macd_hist is not None:
        signals["macd"] = "BULLISH" if macd_hist > 0 else "BEARISH"

    # Trend (price vs key MAs)
    sma_200 = ti.get("sma_200")
    sma_50  = ti.get("sma_50")
    if close and sma_200:
        if close > sma_200 and (not sma_50 or close > sma_50):
            signals["trend"] = "STRONG_UPTREND"
        elif close > sma_200:
            signals["trend"] = "UPTREND"
        elif close < sma_200:
            signals["trend"] = "DOWNTREND"
        else:
            signals["trend"] = "NEUTRAL"

    # Bollinger Band position
    bb_upper = ti.get("bb_upper")
    bb_lower = ti.get("bb_lower")
    if close and bb_upper and bb_lower:
        bb_width = bb_upper - bb_lower
        if bb_width > 0:
            pct = (close - bb_lower) / bb_width
            if pct >= 0.9:       signals["bb_position"] = "NEAR_UPPER"
            elif pct <= 0.1:     signals["bb_position"] = "NEAR_LOWER"
            else:                signals["bb_position"] = "MIDDLE"

    return signals


# ─── DB helpers ───────────────────────────────────────────────────────────────

async def _fetch_price_df(stock_id: int, limit: int = 300, timeframe: str = "1d") -> Optional[pd.DataFrame]:
    if timeframe == "1d":
        sql = """
            SELECT price_date, open, high, low, close, volume
            FROM price_data WHERE stock_id = $1
            ORDER BY price_date DESC LIMIT $2
        """
    elif timeframe == "1w":
        sql = """
            SELECT date_trunc('week', price_date)::date AS price_date,
                   (ARRAY_AGG(open  ORDER BY price_date))[1]       AS open,
                   MAX(high)                                        AS high,
                   MIN(low)                                         AS low,
                   (ARRAY_AGG(close ORDER BY price_date DESC))[1]  AS close,
                   SUM(volume)                                      AS volume
            FROM price_data WHERE stock_id = $1
            GROUP BY date_trunc('week', price_date)
            ORDER BY price_date DESC LIMIT $2
        """
    else:
        return None

    async with raw_connection() as conn:
        rows = await conn.fetch(sql, stock_id, limit)

    if not rows:
        return None

    df = pd.DataFrame([dict(r) for r in rows])
    df["price_date"] = pd.to_datetime(df["price_date"])
    df.set_index("price_date", inplace=True)
    df.sort_index(inplace=True)
    df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
    return df


async def _upsert_indicators(stock_id: int, timeframe: str, ind_date, data: dict):
    sql = """
        INSERT INTO technical_indicators
            (stock_id, timeframe, ind_date,
             sma_20, sma_50, sma_200, ema_9, ema_21, ema_50,
             rsi_14, macd_line, macd_signal, macd_hist,
             bb_upper, bb_middle, bb_lower, atr_14, adx_14,
             stoch_k, stoch_d, volume_sma_20)
        VALUES
            ($1, $2, $3,
             $4, $5, $6, $7, $8, $9,
             $10, $11, $12, $13,
             $14, $15, $16, $17, $18,
             $19, $20, $21)
        ON CONFLICT (stock_id, timeframe, ind_date)
        DO UPDATE SET
            sma_20=$4, sma_50=$5, sma_200=$6, ema_9=$7, ema_21=$8, ema_50=$9,
            rsi_14=$10, macd_line=$11, macd_signal=$12, macd_hist=$13,
            bb_upper=$14, bb_middle=$15, bb_lower=$16, atr_14=$17, adx_14=$18,
            stoch_k=$19, stoch_d=$20, volume_sma_20=$21
    """
    d = data
    async with raw_connection() as conn:
        await conn.execute(sql,
            stock_id, timeframe, ind_date,
            d["sma_20"], d["sma_50"], d["sma_200"], d["ema_9"], d["ema_21"], d["ema_50"],
            d["rsi_14"], d["macd_line"], d["macd_signal"], d["macd_hist"],
            d["bb_upper"], d["bb_middle"], d["bb_lower"], d["atr_14"], d["adx_14"],
            d["stoch_k"], d["stoch_d"], d["volume_sma_20"],
        )


async def _fetch_active_stocks() -> list:
    async with raw_connection() as conn:
        rows = await conn.fetch(
            "SELECT id, symbol FROM stocks WHERE is_active=TRUE AND is_index=FALSE ORDER BY id"
        )
        return [dict(r) for r in rows]


def _s(row, col) -> Optional[float]:
    """Safe float extraction from pandas Series."""
    try:
        v = row.get(col)
        if v is None or pd.isna(v):
            return None
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None
```

---

## 5.2 Pattern Recognition Engine

Create `backend/pipeline/pattern_engine.py`:

```python
# backend/pipeline/pattern_engine.py
"""
Detects chart patterns from stored OHLCV data.
All logic is algorithmic — no ML.
Uses scipy.signal.argrelextrema for peak/trough detection.
"""

import logging
import json
from dataclasses import dataclass, field
from typing import Optional
from datetime import date
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
from pipeline.audit import audit_job
from pipeline.technical_engine import _fetch_price_df
from app.database import raw_connection

logger = logging.getLogger(__name__)


# ─── Data structure ───────────────────────────────────────────────────────────

@dataclass
class PatternResult:
    pattern_type:   str
    direction:      str     # 'BULLISH' | 'BEARISH'
    breakout_level: float
    confidence:     float   # 0.0 – 1.0
    start_date:     date
    end_date:       date
    metadata:       dict    = field(default_factory=dict)


# ─── Main entry points ────────────────────────────────────────────────────────

async def run_pattern_detection():
    async with audit_job("pattern_detection") as audit:
        stocks = await _fetch_active_stocks()
        total = 0
        for stock in stocks:
            try:
                patterns = await detect_patterns_for_stock(stock["id"])
                for p in patterns:
                    await _store_pattern(stock["id"], p)
                total += len(patterns)
            except Exception as e:
                logger.error(f"Pattern detection failed for {stock['symbol']}: {e}")
        audit.records_out = total


async def detect_patterns_for_stock(stock_id: int, timeframe: str = "1d") -> list[PatternResult]:
    df = await _fetch_price_df(stock_id, limit=300, timeframe=timeframe)
    if df is None or len(df) < 100:
        return []

    detector = PatternDetector(df)
    return detector.detect_all()


# ─── Pattern Detector Class ───────────────────────────────────────────────────

class PatternDetector:
    def __init__(self, df: pd.DataFrame, order: int = 5):
        self.df    = df
        self.order = order

        highs = df["high"].values
        lows  = df["low"].values

        # argrelextrema finds local maxima/minima
        self.peak_idx   = argrelextrema(highs, np.greater_equal, order=order)[0]
        self.trough_idx = argrelextrema(lows,  np.less_equal,    order=order)[0]

    def detect_all(self) -> list[PatternResult]:
        results = []
        for fn in [
            self.detect_double_top,
            self.detect_double_bottom,
            self.detect_head_and_shoulders,
            self.detect_inv_head_and_shoulders,
            self.detect_breakout,
            self.detect_breakdown,
        ]:
            result = fn()
            if result:
                results.append(result)
        return results

    # ─── Double Top ───────────────────────────────────────────────────────────
    def detect_double_top(self) -> Optional[PatternResult]:
        """
        Two highs within 3% of each other, separated by a trough at least 5% below peaks.
        """
        peaks = self.peak_idx[-8:]  # look at last 8 local highs
        for i in range(len(peaks) - 1):
            p1, p2 = peaks[i], peaks[i + 1]
            h1 = float(self.df["high"].iloc[p1])
            h2 = float(self.df["high"].iloc[p2])
            peak_max = max(h1, h2)
            similarity = 1 - abs(h1 - h2) / peak_max

            if similarity < 0.97:   # peaks must be within 3%
                continue

            # Neckline = trough between the two peaks
            trough_region = self.df["low"].iloc[p1:p2 + 1]
            neckline = float(trough_region.min())
            depth = (peak_max - neckline) / peak_max

            if depth < 0.05:        # need at least 5% depth
                continue

            return PatternResult(
                "DOUBLE_TOP", "BEARISH", neckline,
                round(similarity, 3),
                self.df.index[p1].date() if hasattr(self.df.index[p1], "date") else self.df.index[p1],
                self.df.index[p2].date() if hasattr(self.df.index[p2], "date") else self.df.index[p2],
                {"peak1": h1, "peak2": h2, "neckline": neckline, "depth_pct": round(depth * 100, 2)},
            )
        return None

    # ─── Double Bottom ────────────────────────────────────────────────────────
    def detect_double_bottom(self) -> Optional[PatternResult]:
        """Two lows within 3% of each other, separated by a peak at least 5% above."""
        troughs = self.trough_idx[-8:]
        for i in range(len(troughs) - 1):
            t1, t2 = troughs[i], troughs[i + 1]
            l1 = float(self.df["low"].iloc[t1])
            l2 = float(self.df["low"].iloc[t2])
            trough_min = min(l1, l2)
            similarity = 1 - abs(l1 - l2) / trough_min if trough_min != 0 else 0

            if similarity < 0.97:
                continue

            resistance = float(self.df["high"].iloc[t1:t2 + 1].max())
            depth = (resistance - trough_min) / resistance if resistance != 0 else 0

            if depth < 0.05:
                continue

            return PatternResult(
                "DOUBLE_BOTTOM", "BULLISH", resistance,
                round(similarity, 3),
                self.df.index[t1].date() if hasattr(self.df.index[t1], "date") else self.df.index[t1],
                self.df.index[t2].date() if hasattr(self.df.index[t2], "date") else self.df.index[t2],
                {"trough1": l1, "trough2": l2, "resistance": resistance, "depth_pct": round(depth * 100, 2)},
            )
        return None

    # ─── Head and Shoulders ───────────────────────────────────────────────────
    def detect_head_and_shoulders(self) -> Optional[PatternResult]:
        """
        Three peaks: left shoulder < head > right shoulder.
        Shoulders within 5% of each other.
        """
        peaks = self.peak_idx[-10:]
        for i in range(len(peaks) - 2):
            ls_idx, head_idx, rs_idx = peaks[i], peaks[i + 1], peaks[i + 2]
            h_ls   = float(self.df["high"].iloc[ls_idx])
            h_head = float(self.df["high"].iloc[head_idx])
            h_rs   = float(self.df["high"].iloc[rs_idx])

            # Head must be highest
            if not (h_head > h_ls and h_head > h_rs):
                continue
            # Shoulders must be within 5% of each other
            shoulder_similarity = 1 - abs(h_ls - h_rs) / max(h_ls, h_rs)
            if shoulder_similarity < 0.95:
                continue

            # Neckline = average of the two troughs between shoulders and head
            left_neckline  = float(self.df["low"].iloc[ls_idx:head_idx + 1].min())
            right_neckline = float(self.df["low"].iloc[head_idx:rs_idx + 1].min())
            neckline = (left_neckline + right_neckline) / 2

            return PatternResult(
                "HEAD_SHOULDERS", "BEARISH", neckline,
                round(shoulder_similarity, 3),
                self.df.index[ls_idx].date() if hasattr(self.df.index[ls_idx], "date") else self.df.index[ls_idx],
                self.df.index[rs_idx].date() if hasattr(self.df.index[rs_idx], "date") else self.df.index[rs_idx],
                {"left_shoulder": h_ls, "head": h_head, "right_shoulder": h_rs, "neckline": neckline},
            )
        return None

    # ─── Inverse Head and Shoulders ───────────────────────────────────────────
    def detect_inv_head_and_shoulders(self) -> Optional[PatternResult]:
        """Three troughs: left shoulder > head < right shoulder."""
        troughs = self.trough_idx[-10:]
        for i in range(len(troughs) - 2):
            ls, head, rs = troughs[i], troughs[i + 1], troughs[i + 2]
            l_ls   = float(self.df["low"].iloc[ls])
            l_head = float(self.df["low"].iloc[head])
            l_rs   = float(self.df["low"].iloc[rs])

            if not (l_head < l_ls and l_head < l_rs):
                continue
            shoulder_sim = 1 - abs(l_ls - l_rs) / max(abs(l_ls), abs(l_rs)) if max(abs(l_ls), abs(l_rs)) else 0
            if shoulder_sim < 0.95:
                continue

            left_resistance  = float(self.df["high"].iloc[ls:head + 1].max())
            right_resistance = float(self.df["high"].iloc[head:rs + 1].max())
            neckline = (left_resistance + right_resistance) / 2

            return PatternResult(
                "INV_HEAD_SHOULDERS", "BULLISH", neckline,
                round(shoulder_sim, 3),
                self.df.index[ls].date() if hasattr(self.df.index[ls], "date") else self.df.index[ls],
                self.df.index[rs].date() if hasattr(self.df.index[rs], "date") else self.df.index[rs],
                {"left_shoulder": l_ls, "head": l_head, "right_shoulder": l_rs, "neckline": neckline},
            )
        return None

    # ─── Breakout ─────────────────────────────────────────────────────────────
    def detect_breakout(self) -> Optional[PatternResult]:
        """Close above 52-week high on above-average volume (1.5x 20-day average)."""
        if len(self.df) < 252:
            return None

        curr     = self.df.iloc[-1]
        high_52w = float(self.df["high"].iloc[-252:-1].max())
        avg_vol  = float(self.df["volume"].iloc[-20:].mean())

        if float(curr["close"]) > high_52w and float(curr["volume"]) > 1.5 * avg_vol:
            vol_ratio = float(curr["volume"]) / avg_vol if avg_vol else 0
            curr_date = self.df.index[-1].date() if hasattr(self.df.index[-1], "date") else self.df.index[-1]
            return PatternResult(
                "BREAKOUT", "BULLISH", high_52w, min(0.95, round(vol_ratio / 3, 3)),
                curr_date, curr_date,
                {"resistance": high_52w, "volume_ratio": round(vol_ratio, 2)},
            )
        return None

    # ─── Breakdown ────────────────────────────────────────────────────────────
    def detect_breakdown(self) -> Optional[PatternResult]:
        """Close below 52-week low on above-average volume."""
        if len(self.df) < 252:
            return None

        curr     = self.df.iloc[-1]
        low_52w  = float(self.df["low"].iloc[-252:-1].min())
        avg_vol  = float(self.df["volume"].iloc[-20:].mean())

        if float(curr["close"]) < low_52w and float(curr["volume"]) > 1.5 * avg_vol:
            vol_ratio = float(curr["volume"]) / avg_vol if avg_vol else 0
            curr_date = self.df.index[-1].date() if hasattr(self.df.index[-1], "date") else self.df.index[-1]
            return PatternResult(
                "BREAKDOWN", "BEARISH", low_52w, min(0.95, round(vol_ratio / 3, 3)),
                curr_date, curr_date,
                {"support": low_52w, "volume_ratio": round(vol_ratio, 2)},
            )
        return None


# ─── DB helpers ───────────────────────────────────────────────────────────────

async def _store_pattern(stock_id: int, p: PatternResult):
    sql = """
        INSERT INTO detected_patterns
            (stock_id, pattern_type, timeframe, detected_on, pattern_start, pattern_end,
             breakout_level, direction, confidence, is_active, metadata)
        VALUES ($1, $2, '1d', $3, $4, $5, $6, $7, $8, TRUE, $9::jsonb)
        ON CONFLICT DO NOTHING
    """
    async with raw_connection() as conn:
        await conn.execute(sql,
            stock_id, p.pattern_type, p.end_date, p.start_date, p.end_date,
            p.breakout_level, p.direction, p.confidence, json.dumps(p.metadata)
        )


async def _fetch_active_stocks() -> list:
    async with raw_connection() as conn:
        rows = await conn.fetch(
            "SELECT id, symbol FROM stocks WHERE is_active=TRUE AND is_index=FALSE ORDER BY id"
        )
        return [dict(r) for r in rows]
```

---

## 5.3 Enable Jobs in Scheduler

```python
# In pipeline/scheduler.py — uncomment:
from pipeline.technical_engine import run_technical_indicators
from pipeline.pattern_engine import run_pattern_detection

scheduler.add_job(
    run_technical_indicators,
    CronTrigger(day_of_week="mon-fri", hour=19, minute=0),
    max_instances=1, id="technicals"
)
scheduler.add_job(
    run_pattern_detection,
    CronTrigger(day_of_week="mon-fri", hour=19, minute=45),
    max_instances=1, id="patterns"
)
```

---

## 5.4 API Endpoints

Create `backend/app/routers/technicals.py`:

```python
# backend/app/routers/technicals.py
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from app.database import get_db
from app.routers.stocks import _get_stock_id
from pipeline.technical_engine import interpret_signals

router = APIRouter()

@router.get("/stocks/{symbol}/technicals")
async def get_technicals(
    symbol:    str,
    timeframe: str = Query("1d", regex="^(1d|1w|1mo)$"),
    db: AsyncSession = Depends(get_db),
):
    stock = await _get_stock_id(symbol, db)
    if not stock:
        raise HTTPException(404, f"Stock '{symbol}' not found")

    sql = """
        SELECT ti.*, p.close AS latest_close
        FROM technical_indicators ti
        CROSS JOIN LATERAL (
            SELECT close FROM price_data WHERE stock_id = :sid ORDER BY price_date DESC LIMIT 1
        ) p
        WHERE ti.stock_id = :sid AND ti.timeframe = :tf
        ORDER BY ti.ind_date DESC
        LIMIT 1
    """
    result = await db.execute(text(sql), {"sid": stock["id"], "tf": timeframe})
    row = result.fetchone()
    if not row:
        raise HTTPException(404, f"No technical data for '{symbol}' (timeframe={timeframe})")

    ti_data = dict(row._mapping)
    close   = ti_data.pop("latest_close", None)
    signals = interpret_signals(ti_data, close) if close else {}

    return {"symbol": symbol.upper(), "timeframe": timeframe, "indicators": ti_data, "signals": signals}


@router.get("/stocks/{symbol}/patterns")
async def get_patterns(
    symbol:      str,
    active_only: bool = True,
    limit:       int  = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    stock = await _get_stock_id(symbol, db)
    if not stock:
        raise HTTPException(404, f"Stock '{symbol}' not found")

    where = "stock_id = :sid"
    if active_only:
        where += " AND is_active = TRUE"

    sql = f"""
        SELECT pattern_type, timeframe, detected_on, pattern_start, pattern_end,
               breakout_level, direction, confidence, metadata
        FROM detected_patterns
        WHERE {where}
        ORDER BY detected_on DESC
        LIMIT :limit
    """
    result = await db.execute(text(sql), {"sid": stock["id"], "limit": limit})
    return {"symbol": symbol.upper(), "patterns": [dict(r._mapping) for r in result.fetchall()]}
```

Register in `main.py`:

```python
from app.routers import technicals as technicals_router
app.include_router(technicals_router.router, prefix="/api/v1", tags=["Technicals"])
```

---

## 5.5 Frontend — Candlestick Chart & Technical Sub-charts

Install `lightweight-charts`:
```bash
cd frontend && npm install lightweight-charts
```

Create `frontend/src/components/charts/CandlestickChart.jsx`:

```jsx
// frontend/src/components/charts/CandlestickChart.jsx
import { useEffect, useRef, useState } from "react";
import { createChart } from "lightweight-charts";
import stockService from "../../api/stockService";

const INTERVALS = [
  { label: "1M",  value: "1d", limit: 22  },
  { label: "3M",  value: "1d", limit: 66  },
  { label: "6M",  value: "1d", limit: 130 },
  { label: "1Y",  value: "1d", limit: 252 },
  { label: "5Y",  value: "1w", limit: 260 },
];

export default function CandlestickChart({ symbol, indicators }) {
  const chartRef    = useRef(null);
  const chartObj    = useRef(null);
  const candleSeries= useRef(null);
  const [activeInterval, setActiveInterval] = useState(INTERVALS[3]);
  const [showSMA50, setShowSMA50] = useState(true);
  const [showSMA200, setShowSMA200] = useState(true);
  const [showBB,    setShowBB]    = useState(false);

  useEffect(() => {
    if (!chartRef.current) return;

    // Create chart
    const chart = createChart(chartRef.current, {
      width:  chartRef.current.offsetWidth,
      height: 420,
      layout: { background: { color: "transparent" }, textColor: "#94A3B8" },
      grid:   { vertLines: { color: "#1E293B" }, horzLines: { color: "#1E293B" } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "#334155" },
      timeScale:       { borderColor: "#334155", timeVisible: true },
    });

    candleSeries.current = chart.addCandlestickSeries({
      upColor:   "#22C55E", downColor: "#EF4444",
      borderVisible: false,
      wickUpColor:   "#22C55E", wickDownColor: "#EF4444",
    });

    chartObj.current = chart;

    const resizeObserver = new ResizeObserver(() => {
      chart.applyOptions({ width: chartRef.current.offsetWidth });
    });
    resizeObserver.observe(chartRef.current);

    return () => {
      chart.remove();
      resizeObserver.disconnect();
    };
  }, []);

  // Load data when symbol or interval changes
  useEffect(() => {
    if (!symbol || !candleSeries.current) return;

    stockService.getPriceHistory(symbol, {
      interval: activeInterval.value,
      limit:    activeInterval.limit,
    }).then(({ data }) => {
      const candles = data.map(d => ({
        time:  d.time,
        open:  d.open,
        high:  d.high,
        low:   d.low,
        close: d.close,
      }));
      candleSeries.current.setData(candles);

      // Overlay SMA-50
      if (showSMA50 && indicators?.sma_50) {
        // In a full implementation, fetch historical indicator data
        // For now, just show the latest value as a horizontal line
      }
    });
  }, [symbol, activeInterval]);

  return (
    <div className="cal-chart-wrapper">
      {/* Interval selector */}
      <div className="cal-chart-controls">
        <div className="cal-interval-group">
          {INTERVALS.map(iv => (
            <button
              key={iv.label}
              className={`cal-chip cal-chip--sm ${activeInterval.label === iv.label ? "cal-chip--active" : ""}`}
              onClick={() => setActiveInterval(iv)}
            >{iv.label}</button>
          ))}
        </div>
        <div className="cal-overlay-toggles">
          <label className="cal-toggle">
            <input type="checkbox" checked={showSMA50}  onChange={e => setShowSMA50(e.target.checked)}  /> SMA 50
          </label>
          <label className="cal-toggle">
            <input type="checkbox" checked={showSMA200} onChange={e => setShowSMA200(e.target.checked)} /> SMA 200
          </label>
          <label className="cal-toggle">
            <input type="checkbox" checked={showBB}     onChange={e => setShowBB(e.target.checked)}     /> Bollinger
          </label>
        </div>
      </div>

      {/* Chart container */}
      <div ref={chartRef} className="cal-chart" />
    </div>
  );
}
```

Create `frontend/src/components/charts/RSIChart.jsx` using Recharts (already installed):

```jsx
// frontend/src/components/charts/RSIChart.jsx
import { LineChart, Line, XAxis, YAxis, ReferenceLine, Tooltip, ResponsiveContainer } from "recharts";

export default function RSIChart({ data }) {
  // data: [{time, rsi_14}]
  return (
    <div className="cal-subchart">
      <span className="cal-subchart-label">RSI (14)</span>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <XAxis dataKey="time" tick={{ fill: "#64748B", fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fill: "#64748B", fontSize: 10 }} />
          <ReferenceLine y={70} stroke="#EF4444" strokeDasharray="3 3" />
          <ReferenceLine y={30} stroke="#22C55E" strokeDasharray="3 3" />
          <Tooltip contentStyle={{ background: "#1E293B", border: "none" }} />
          <Line type="monotone" dataKey="rsi_14" stroke="#A78BFA" dot={false} strokeWidth={1.5} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

---

## 5.6 Validation Checklist

```bash
# 1. Test pandas-ta on sample data
python3 -c "
import pandas as pd, pandas_ta as ta
df = pd.DataFrame({'open':[100,101,102], 'high':[103,104,105],
                   'low':[99,100,101], 'close':[101,102,103], 'volume':[1e6,1.2e6,0.8e6]})
df.ta.rsi(length=2, append=True)
print(df.filter(like='RSI'))
"

# 2. Run indicators for one stock
python3 -c "
import asyncio
from pipeline.technical_engine import compute_indicators_for_stock
asyncio.run(compute_indicators_for_stock(1, '1d'))
print('Done')
"

# 3. Verify DB
psql -U user -d nivesh -c "
  SELECT ind_date, sma_50, sma_200, rsi_14, macd_hist
  FROM technical_indicators WHERE stock_id=1 AND timeframe='1d'
  ORDER BY ind_date DESC LIMIT 3;
"

# 4. Test pattern detection
python3 -c "
import asyncio
from pipeline.pattern_engine import detect_patterns_for_stock
patterns = asyncio.run(detect_patterns_for_stock(1))
for p in patterns:
    print(p.pattern_type, p.direction, p.confidence)
"

# 5. API tests
curl "http://localhost:8000/api/v1/stocks/RELIANCE/technicals" | jq '{rsi: .indicators.rsi_14, trend: .signals.trend}'
curl "http://localhost:8000/api/v1/stocks/RELIANCE/patterns" | jq '.patterns | length'

# 6. Frontend — candlestick chart renders at http://localhost:5173/#/stocks/RELIANCE
```

---

## 5.7 Deliverables for Phase 5

- [ ] `pipeline/technical_engine.py` implemented and tested
- [ ] `pipeline/pattern_engine.py` implemented — all 6 patterns
- [ ] All 6 pattern detection functions tested on synthetic price series
- [ ] Indicator job scheduled (Mon-Fri 19:00 IST)
- [ ] Pattern job scheduled (Mon-Fri 19:45 IST)
- [ ] `GET /stocks/{symbol}/technicals` returns indicators + signal labels
- [ ] `GET /stocks/{symbol}/patterns` returns detected patterns
- [ ] `CandlestickChart.jsx` renders and fetches price data from API
- [ ] `RSIChart.jsx` renders RSI with overbought/oversold reference lines
- [ ] StockDetail Chart tab fully implemented
- [ ] StockDetail Analysis tab shows RSI, MACD sub-charts
- [ ] `PatternAlertBanner.jsx` shown on StockDetail Overview if active patterns exist
