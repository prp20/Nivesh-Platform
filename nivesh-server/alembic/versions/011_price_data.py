"""011 — price_data table

Revision ID: 011
Revises: 010
"""
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE price_data (
            id         BIGSERIAL      PRIMARY KEY,
            stock_id   INTEGER        NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
            price_date DATE           NOT NULL,
            open       NUMERIC(12, 4),
            high       NUMERIC(12, 4),
            low        NUMERIC(12, 4),
            close      NUMERIC(12, 4) NOT NULL,
            adj_close  NUMERIC(12, 4),
            volume     BIGINT,
            UNIQUE (stock_id, price_date)
        );
    """)
    op.execute("""
        CREATE INDEX ix_price_data_stock_date_desc ON price_data (stock_id, price_date DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS price_data CASCADE;")
