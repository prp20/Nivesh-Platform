"""006 — fund_metrics table

Revision ID: 006
Revises: 005
"""
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fund_metrics (
            scheme_code                   VARCHAR(50)    PRIMARY KEY
                                              REFERENCES fund_master (scheme_code) ON DELETE CASCADE,
            current_nav                   NUMERIC(15, 4) NOT NULL,
            nav_date                      DATE           NOT NULL,
            aum_in_crores                 NUMERIC(18, 2),
            expense_ratio                 NUMERIC(5, 4),
            fund_rating                   NUMERIC(5, 2),
            volatility                    NUMERIC(10, 4),
            cagr_3year                    NUMERIC(10, 4),
            cagr_5year                    NUMERIC(10, 4),
            absolute_return_1y            NUMERIC(10, 4),
            absolute_return_3y            NUMERIC(10, 4),
            absolute_return_5y            NUMERIC(10, 4),
            absolute_return_10y           NUMERIC(10, 4),
            short_term_return_6m          NUMERIC(10, 4),
            upside_capture                NUMERIC(10, 4),
            downside_capture              NUMERIC(10, 4),
            sortino_ratio                 NUMERIC(10, 4),
            sharpe_ratio                  NUMERIC(10, 4),
            alpha                         NUMERIC(10, 4),
            beta                          NUMERIC(10, 4),
            standard_deviation            NUMERIC(10, 4),
            maximum_drawdown              NUMERIC(10, 4),
            tracking_error                NUMERIC(10, 4),
            information_ratio             NUMERIC(10, 4),
            metrics_calculated_at         TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
            calculation_period_start_date DATE,
            calculation_period_end_date   DATE,
            has_sufficient_data           BOOLEAN        NOT NULL DEFAULT TRUE,
            data_completeness_percentage  NUMERIC(5, 2),
            final_verdict                 VARCHAR(1000),
            updated_at                    TIMESTAMPTZ    NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE TRIGGER trg_fund_metrics_updated_at
            BEFORE UPDATE ON fund_metrics
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fund_metrics CASCADE;")
