"""Async SQLAlchemy query helpers used by all agent node functions."""
from __future__ import annotations

from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_fund_master(session: AsyncSession, scheme_code: str) -> dict | None:
    row = await session.execute(
        text("""
            SELECT scheme_code, scheme_name, amc_name, scheme_category, scheme_subcategory,
                   plan_type, benchmark_index_code, inception_date, isin, is_active
            FROM fund_master WHERE scheme_code = :code
        """),
        {"code": scheme_code},
    )
    r = row.fetchone()
    return dict(r._mapping) if r else None


async def fetch_fund_metrics(session: AsyncSession, scheme_code: str) -> dict | None:
    row = await session.execute(
        text("SELECT * FROM fund_metrics WHERE scheme_code = :code"),
        {"code": scheme_code},
    )
    r = row.fetchone()
    return dict(r._mapping) if r else None


async def fetch_peers(
    session: AsyncSession, category: str, exclude_code: str, limit: int = 50
) -> list[dict]:
    rows = await session.execute(
        text("""
            SELECT fm.scheme_code, fm.scheme_name, fm.amc_name,
                   mx.cagr_3year, mx.cagr_5year, mx.sharpe_ratio, mx.alpha,
                   mx.sortino_ratio, mx.maximum_drawdown, mx.expense_ratio
            FROM fund_master fm
            JOIN fund_metrics mx ON mx.scheme_code = fm.scheme_code
            WHERE fm.scheme_category = :cat
              AND fm.scheme_code != :excl
              AND fm.is_active = TRUE
            ORDER BY mx.cagr_3year DESC NULLS LAST
            LIMIT :lim
        """),
        {"cat": category, "excl": exclude_code, "lim": limit},
    )
    return [dict(r._mapping) for r in rows.fetchall()]


async def fetch_stock(session: AsyncSession, symbol: str) -> dict | None:
    row = await session.execute(
        text("""
            SELECT id, symbol, company_name, sector, industry, market_cap_cat,
                   nse_symbol, bse_code, yf_symbol, is_active, is_index
            FROM stocks WHERE symbol = :sym AND is_active = TRUE
        """),
        {"sym": symbol},
    )
    r = row.fetchone()
    return dict(r._mapping) if r else None


async def fetch_latest_price(session: AsyncSession, stock_id: int) -> dict | None:
    row = await session.execute(
        text("""
            SELECT close, open, high, low, volume, price_date
            FROM price_data WHERE stock_id = :sid
            ORDER BY price_date DESC LIMIT 1
        """),
        {"sid": stock_id},
    )
    r = row.fetchone()
    return dict(r._mapping) if r else None


async def fetch_latest_ratios(session: AsyncSession, stock_id: int) -> dict | None:
    row = await session.execute(
        text("""
            SELECT * FROM financial_ratios
            WHERE stock_id = :sid AND period_type = 'annual'
            ORDER BY period_end DESC LIMIT 1
        """),
        {"sid": stock_id},
    )
    r = row.fetchone()
    return dict(r._mapping) if r else None


async def fetch_latest_technical(session: AsyncSession, stock_id: int) -> dict | None:
    row = await session.execute(
        text("""
            SELECT * FROM technical_indicators
            WHERE stock_id = :sid AND timeframe = '1d'
            ORDER BY ind_date DESC LIMIT 1
        """),
        {"sid": stock_id},
    )
    r = row.fetchone()
    return dict(r._mapping) if r else None


async def fetch_latest_financials(session: AsyncSession, stock_id: int) -> dict[str, dict]:
    """Return the latest P&L, Balance Sheet, Cash Flow as {type: data_dict}."""
    rows = await session.execute(
        text("""
            SELECT statement_type, data, period_end FROM financial_statements
            WHERE stock_id = :sid AND period_type = 'annual'
            AND (statement_type, period_end) IN (
                SELECT statement_type, MAX(period_end)
                FROM financial_statements
                WHERE stock_id = :sid AND period_type = 'annual'
                GROUP BY statement_type
            )
        """),
        {"sid": stock_id},
    )
    result: dict[str, Any] = {}
    for r in rows.fetchall():
        result[r.statement_type] = r.data or {}
    return result


async def fetch_stock_rating(session: AsyncSession, stock_id: int) -> dict | None:
    row = await session.execute(
        text("""
            SELECT total_score, rating_label, fundamental_score, valuation_score,
                   technical_score, momentum_score, shareholding_score, rated_on
            FROM stock_ratings WHERE stock_id = :sid
            ORDER BY rated_on DESC LIMIT 1
        """),
        {"sid": stock_id},
    )
    r = row.fetchone()
    return dict(r._mapping) if r else None


async def fetch_sector_median_ratios(session: AsyncSession, sector: str, stock_id: int) -> dict:
    """Compute sector median PE, PB, PS, EV/EBITDA for valuation comparison."""
    row = await session.execute(
        text("""
            SELECT
                AVG(fr.pe_ratio)   AS median_pe,
                AVG(fr.pb_ratio)   AS median_pb,
                AVG(fr.ps_ratio)   AS median_ps,
                AVG(fr.ev_ebitda)  AS median_ev_ebitda
            FROM financial_ratios fr
            JOIN stocks s ON s.id = fr.stock_id
            WHERE s.sector = :sector
              AND s.is_active = TRUE
              AND fr.stock_id != :sid
              AND fr.period_type = 'annual'
              AND fr.period_end = (
                  SELECT MAX(fr2.period_end) FROM financial_ratios fr2
                  WHERE fr2.stock_id = fr.stock_id AND fr2.period_type = 'annual'
              )
        """),
        {"sector": sector, "sid": stock_id},
    )
    r = row.fetchone()
    return dict(r._mapping) if r else {}


async def fetch_latest_stock_analysis(session: AsyncSession, symbol: str) -> dict | None:
    row = await session.execute(
        text("""
            SELECT * FROM agent_stock_analysis
            WHERE symbol = :sym AND status = 'COMPLETED'
            ORDER BY analysed_at DESC LIMIT 1
        """),
        {"sym": symbol},
    )
    r = row.fetchone()
    return dict(r._mapping) if r else None
