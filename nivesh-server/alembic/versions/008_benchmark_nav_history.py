"""008 — benchmark_nav_history table

Revision ID: 008
Revises: 007
"""
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE benchmark_nav_history (
            benchmark_code VARCHAR(50)    NOT NULL
                               REFERENCES benchmark_master (benchmark_code) ON DELETE CASCADE,
            nav_date       DATE           NOT NULL,
            index_value    NUMERIC(15, 4) NOT NULL,
            created_at     TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
            PRIMARY KEY (benchmark_code, nav_date)
        );
    """)
    op.execute("""
        CREATE INDEX ix_benchmark_nav_history_nav_date ON benchmark_nav_history (nav_date);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS benchmark_nav_history CASCADE;")
