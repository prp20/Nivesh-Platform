"""Add fundamental_scores table

Revision ID: b59293c1bdc7
Revises: 002
Create Date: 2026-04-18 23:46:18.308188

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b59293c1bdc7'
down_revision: Union[str, Sequence[str], None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'fundamental_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('period_type', sa.String(length=10), nullable=False),
        sa.Column('pl_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('bs_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('cf_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('pl_growth_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('pl_margin_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('pl_eps_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('pl_consistency_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('bs_leverage_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('bs_liquidity_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('bs_asset_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('bs_networth_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('cf_operating_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('cf_capex_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('cf_financing_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('composite_fundamental_score', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('reasoning_label', sa.String(length=50), nullable=True),
        sa.Column('reasoning_text', sa.Text(), nullable=True),
        sa.Column('score_version', sa.String(length=10), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'period_end', 'score_version', name='uq_stock_period_version')
    )
    op.create_index(op.f('ix_fundamental_scores_stock_id'), 'fundamental_scores', ['stock_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_fundamental_scores_stock_id'), table_name='fundamental_scores')
    op.drop_table('fundamental_scores')
