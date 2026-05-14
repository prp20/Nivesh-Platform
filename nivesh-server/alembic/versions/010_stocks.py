"""010 — stocks table

Revision ID: 010
Revises: 009
"""
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE stocks (
            id             SERIAL        PRIMARY KEY,
            symbol         VARCHAR(20)   NOT NULL UNIQUE,
            nse_symbol     VARCHAR(20),
            bse_code       VARCHAR(10),
            yf_symbol      VARCHAR(30)   NOT NULL,
            screener_slug  VARCHAR(50),
            company_name   VARCHAR(255)  NOT NULL,
            sector         VARCHAR(100),
            industry       VARCHAR(100),
            summary        VARCHAR(5000),
            market_cap_cat VARCHAR(50),
            is_index       BOOLEAN       NOT NULL DEFAULT FALSE,
            is_active      BOOLEAN       NOT NULL DEFAULT TRUE,
            data_quality   VARCHAR(10)   NOT NULL DEFAULT 'OK',
            created_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            updated_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_stocks_sector     ON stocks (sector);")
    op.execute("CREATE INDEX idx_stocks_is_active  ON stocks (is_active);")
    op.execute("CREATE INDEX idx_stocks_market_cap ON stocks (market_cap_cat);")
    op.execute("""
        CREATE TRIGGER trg_stocks_updated_at
            BEFORE UPDATE ON stocks
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS stocks CASCADE;")
