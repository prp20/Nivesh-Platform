"""009 — benchmark_metrics table

Revision ID: 009
Revises: 008
"""
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE benchmark_metrics (
            benchmark_code        VARCHAR(50)    PRIMARY KEY
                                      REFERENCES benchmark_master (benchmark_code) ON DELETE CASCADE,
            current_nav           NUMERIC(15, 4) NOT NULL,
            nav_date              DATE           NOT NULL,
            cagr_3year            NUMERIC(10, 4),
            cagr_5year            NUMERIC(10, 4),
            sortino_ratio         NUMERIC(10, 4),
            sharpe_ratio          NUMERIC(10, 4),
            standard_deviation    NUMERIC(10, 4),
            maximum_drawdown      NUMERIC(10, 4),
            metrics_calculated_at TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
            updated_at            TIMESTAMPTZ    NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE TRIGGER trg_benchmark_metrics_updated_at
            BEFORE UPDATE ON benchmark_metrics
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS benchmark_metrics CASCADE;")
