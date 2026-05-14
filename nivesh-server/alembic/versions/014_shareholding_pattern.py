"""014 — shareholding_pattern table

Revision ID: 014
Revises: 013
"""
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE shareholding_pattern (
            id              SERIAL       PRIMARY KEY,
            stock_id        INTEGER      NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
            period_end      DATE         NOT NULL,
            promoter_pct    NUMERIC(6, 3),
            fii_pct         NUMERIC(6, 3),
            dii_pct         NUMERIC(6, 3),
            public_pct      NUMERIC(6, 3),
            pledged_pct     NUMERIC(6, 3),
            promoter_change NUMERIC(6, 3),
            fii_change      NUMERIC(6, 3),
            scraped_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            UNIQUE (stock_id, period_end)
        );
    """)
    op.execute("""
        CREATE INDEX ix_shareholding_pattern_stock_period
            ON shareholding_pattern (stock_id, period_end DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS shareholding_pattern CASCADE;")
