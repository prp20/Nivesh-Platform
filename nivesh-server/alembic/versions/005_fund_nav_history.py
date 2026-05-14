"""005 — fund_nav_history table

Revision ID: 005
Revises: 004
"""
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fund_nav_history (
            scheme_code VARCHAR(50)    NOT NULL
                            REFERENCES fund_master (scheme_code) ON DELETE CASCADE,
            nav_date    DATE           NOT NULL,
            nav_value   NUMERIC(15, 4) NOT NULL,
            created_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
            PRIMARY KEY (scheme_code, nav_date)
        );
    """)
    op.execute("""
        CREATE INDEX ix_fund_nav_history_nav_date ON fund_nav_history (nav_date);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fund_nav_history CASCADE;")
