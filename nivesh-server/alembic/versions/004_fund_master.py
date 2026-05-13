"""004 — fund_master table

Revision ID: 004
Revises: 003
"""
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fund_master (
            scheme_code          VARCHAR(50)  PRIMARY KEY,
            scheme_name          VARCHAR(500) NOT NULL,
            amc_name             VARCHAR(200) NOT NULL,
            inception_date       DATE         NOT NULL,
            plan_type            VARCHAR(20)  NOT NULL,
            scheme_category      VARCHAR(100) NOT NULL,
            scheme_subcategory   VARCHAR(100),
            benchmark_index_code VARCHAR(50),
            isin                 VARCHAR(50)  UNIQUE,
            manager_experience   VARCHAR(500),
            is_active            BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX ix_fund_master_amc_name_trgm
            ON fund_master USING GIN (amc_name gin_trgm_ops);
    """)
    op.execute("""
        CREATE INDEX ix_fund_master_scheme_category_trgm
            ON fund_master USING GIN (scheme_category gin_trgm_ops);
    """)
    op.execute("CREATE INDEX ix_fund_master_plan_type ON fund_master (plan_type);")
    op.execute("CREATE INDEX ix_fund_master_is_active ON fund_master (is_active);")
    op.execute("""
        CREATE TRIGGER trg_fund_master_updated_at
            BEFORE UPDATE ON fund_master
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fund_master CASCADE;")
