"""
Local data router — /local/*

All endpoints operate exclusively on SQLite.
No server calls. No auth required (local machine = trusted).

Routes:
  GET/POST   /local/watchlist
  DELETE     /local/watchlist/{id}
  GET/POST   /local/portfolio/holdings
  PUT/DELETE /local/portfolio/holdings/{id}
  GET/POST   /local/portfolio/transactions
  GET        /local/preferences
  PUT        /local/preferences/{key}
"""

import logging
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user_data import (
    PortfolioHolding,
    Transaction,
    UserPreference,
    Watchlist,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/local", tags=["local"])


# ── Pydantic schemas (local only — not shared with server) ────────────────────

class WatchlistCreate(BaseModel):
    symbol: str
    asset_type: str          # 'STOCK' | 'FUND'
    display_name: Optional[str] = None
    notes: Optional[str] = None
    alert_above: Optional[float] = None
    alert_below: Optional[float] = None


class WatchlistRead(WatchlistCreate):
    id: int
    added_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HoldingCreate(BaseModel):
    symbol: str
    asset_type: str
    quantity: float
    avg_cost: float
    buy_date: date
    folio_number: Optional[str] = None
    broker: Optional[str] = None
    notes: Optional[str] = None


class HoldingRead(HoldingCreate):
    id: int

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    symbol: str
    asset_type: str
    txn_type: str
    quantity: float
    price: float
    txn_date: date
    amount: Optional[float] = None
    brokerage: float = 0.0
    notes: Optional[str] = None


# ── Watchlist ─────────────────────────────────────────────────────────────────

@router.get("/watchlist", response_model=List[WatchlistRead])
async def get_watchlist(
    asset_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Watchlist)
    if asset_type:
        q = q.where(Watchlist.asset_type == asset_type.upper())
    result = await db.execute(q.order_by(Watchlist.added_at.desc()))
    return result.scalars().all()


@router.post("/watchlist", response_model=WatchlistRead, status_code=201)
async def add_to_watchlist(
    body: WatchlistCreate, db: AsyncSession = Depends(get_db)
):
    item = Watchlist(**body.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/watchlist/{item_id}", status_code=204)
async def remove_from_watchlist(
    item_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        delete(Watchlist).where(Watchlist.id == item_id)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Watchlist item not found")
    await db.commit()


# ── Portfolio Holdings ────────────────────────────────────────────────────────

@router.get("/portfolio/holdings", response_model=List[HoldingRead])
async def get_holdings(
    asset_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(PortfolioHolding)
    if asset_type:
        q = q.where(PortfolioHolding.asset_type == asset_type.upper())
    result = await db.execute(q.order_by(PortfolioHolding.symbol))
    return result.scalars().all()


@router.post("/portfolio/holdings", response_model=HoldingRead, status_code=201)
async def add_holding(
    body: HoldingCreate, db: AsyncSession = Depends(get_db)
):
    holding = PortfolioHolding(**body.model_dump())
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    return holding


@router.put("/portfolio/holdings/{holding_id}", response_model=HoldingRead)
async def update_holding(
    holding_id: int, body: HoldingCreate, db: AsyncSession = Depends(get_db)
):
    await db.execute(
        update(PortfolioHolding)
        .where(PortfolioHolding.id == holding_id)
        .values(**body.model_dump())
    )
    await db.commit()
    result = await db.execute(
        select(PortfolioHolding).where(PortfolioHolding.id == holding_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Holding not found")
    return row


@router.delete("/portfolio/holdings/{holding_id}", status_code=204)
async def delete_holding(
    holding_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        delete(PortfolioHolding).where(PortfolioHolding.id == holding_id)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Holding not found")
    await db.commit()


# ── Transactions ──────────────────────────────────────────────────────────────

@router.get("/portfolio/transactions")
async def get_transactions(
    symbol: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Transaction)
    if symbol:
        q = q.where(Transaction.symbol == symbol.upper())
    result = await db.execute(q.order_by(Transaction.txn_date.desc()))
    return result.scalars().all()


@router.post("/portfolio/transactions", status_code=201)
async def add_transaction(
    body: TransactionCreate, db: AsyncSession = Depends(get_db)
):
    data = body.model_dump()
    if data.get("amount") is None:
        data["amount"] = data["quantity"] * data["price"]
    txn = Transaction(**data)
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn


# ── Preferences ───────────────────────────────────────────────────────────────

@router.get("/preferences")
async def get_preferences(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserPreference))
    rows = result.scalars().all()
    return {r.key: r.value for r in rows}


@router.put("/preferences/{key}")
async def set_preference(
    key: str, value: str, db: AsyncSession = Depends(get_db)
):
    stmt = sqlite_insert(UserPreference).values(key=key, value=value)
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"], set_={"value": value}
    )
    await db.execute(stmt)
    await db.commit()
    return {"key": key, "value": value}
