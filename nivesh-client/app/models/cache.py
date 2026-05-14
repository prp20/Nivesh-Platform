"""
Unified TTL cache for all server API responses.

A single table avoids multiple cache_stock_xxx, cache_fund_xxx tables.
The cache_key is a namespaced string:
  'funds:list:{hash}'
  'funds:detail:119598'
  'funds:nav:119598:365'
  'funds:compare:{sorted_codes}'
  'stocks:list:{hash}'
  'stocks:detail:RELIANCE'
  'stocks:screener:{hash}'
  'benchmarks:list'
  'etl:status'

data_json stores the raw JSON string of the server response.
The proxy router deserialises it and returns it to the React UI as-is —
preserving the exact shape the UI already expects.
"""

from sqlalchemy import Column, String, Text, Integer, TIMESTAMP
from sqlalchemy.sql import func

from ..database import Base


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    cache_key           = Column(String(500), primary_key=True)
    data_json           = Column(Text, nullable=False)
    fetched_at          = Column(TIMESTAMP, nullable=False, server_default=func.now())
    ttl_seconds         = Column(Integer, nullable=False, default=3600)
    server_generated_at = Column(String(50))
    # ^ Stores the server's generated_at timestamp if present in the response.
    # Used for delta sync bookkeeping — tells us data is fresh up to this point.
