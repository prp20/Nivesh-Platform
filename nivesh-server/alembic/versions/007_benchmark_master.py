"""007 — benchmark_master table

Revision ID: 007
Revises: 006
"""
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE benchmark_master (
            benchmark_code VARCHAR(50)  PRIMARY KEY,
            benchmark_name VARCHAR(200) NOT NULL,
            ticker         VARCHAR(50)  NOT NULL,
            benchmark_type VARCHAR(100),
            asset_class    VARCHAR(50),
            is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE TRIGGER trg_benchmark_master_updated_at
            BEFORE UPDATE ON benchmark_master
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS benchmark_master CASCADE;")
