"""add_extended_stats_to_ratios

Revision ID: e7b9d9f1a2c3
Revises: fdfc78abab15
Create Date: 2026-04-20 22:08:39.658599

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b9d9f1a2c3'
down_revision: Union[str, Sequence[str], None] = 'fdfc78abab15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add extended stats columns to financial_ratios table."""
    conn = op.get_bind()
    # SQLite: tables are created by migration 003 — skip all PostgreSQL-specific DDL
    if conn.dialect.name == 'sqlite':
        return
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('financial_ratios')]

    if 'market_cap' not in columns:
        op.add_column('financial_ratios', sa.Column('market_cap', sa.Numeric(precision=18, scale=4), nullable=True))
    if 'low_52w' not in columns:
        op.add_column('financial_ratios', sa.Column('low_52w', sa.Numeric(precision=12, scale=4), nullable=True))
    if 'high_52w' not in columns:
        op.add_column('financial_ratios', sa.Column('high_52w', sa.Numeric(precision=12, scale=4), nullable=True))
    if 'revenue_per_share' not in columns:
        op.add_column('financial_ratios', sa.Column('revenue_per_share', sa.Numeric(precision=12, scale=4), nullable=True))


def downgrade() -> None:
    """Remove extended stats columns from financial_ratios table."""
    conn = op.get_bind()
    if conn.dialect.name == 'sqlite':
        return
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('financial_ratios')]

    if 'market_cap' in columns:
        op.drop_column('financial_ratios', 'market_cap')
    if 'low_52w' in columns:
        op.drop_column('financial_ratios', 'low_52w')
    if 'high_52w' in columns:
        op.drop_column('financial_ratios', 'high_52w')
    if 'revenue_per_share' in columns:
        op.drop_column('financial_ratios', 'revenue_per_share')
