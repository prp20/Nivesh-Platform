"""012 — financial_statements table

Stores P&L, Balance Sheet, Cash Flow as JSONB per (stock, statement_type, period).
statement_type: 'PL' | 'BS' | 'CF'
period_type: 'annual' | 'quarterly'

Revision ID: 012
Revises: 011
"""
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE financial_statements (
            id             SERIAL       PRIMARY KEY,
            stock_id       INTEGER      NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
            statement_type VARCHAR(5)   NOT NULL,
            period_type    VARCHAR(10)  NOT NULL,
            period_end     DATE         NOT NULL,
            currency       VARCHAR(5)   NOT NULL DEFAULT 'INR',
            data           JSONB        NOT NULL,
            raw_data       JSONB,
            scraped_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            raw_checksum   VARCHAR(64),
            UNIQUE (stock_id, statement_type, period_type, period_end)
        );
    """)
    op.execute("""
        CREATE INDEX ix_financial_stmt_stock_period
            ON financial_statements (stock_id, period_end DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS financial_statements CASCADE;")
