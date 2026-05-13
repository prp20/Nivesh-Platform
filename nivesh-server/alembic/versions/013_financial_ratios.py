"""013 — financial_ratios table

Computed ratios per (stock, period_end, period_type).
Populated nightly by the ratio_engine pipeline.

Revision ID: 013
Revises: 012
"""
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE financial_ratios (
            id                    SERIAL        PRIMARY KEY,
            stock_id              INTEGER       NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
            period_end            DATE          NOT NULL,
            period_type           VARCHAR(10)   NOT NULL,
            pe_ratio              NUMERIC(10, 3),
            pb_ratio              NUMERIC(10, 3),
            ps_ratio              NUMERIC(10, 3),
            ev_ebitda             NUMERIC(10, 3),
            peg_ratio             NUMERIC(10, 3),
            roe                   NUMERIC(10, 3),
            roce                  NUMERIC(10, 3),
            roa                   NUMERIC(10, 3),
            gross_margin          NUMERIC(10, 3),
            ebitda_margin         NUMERIC(10, 3),
            operating_margin      NUMERIC(10, 3),
            pat_margin            NUMERIC(10, 3),
            debt_equity           NUMERIC(10, 3),
            interest_cov          NUMERIC(10, 3),
            current_ratio         NUMERIC(10, 3),
            quick_ratio           NUMERIC(10, 3),
            revenue_growth        NUMERIC(10, 3),
            pat_growth            NUMERIC(10, 3),
            eps_growth            NUMERIC(10, 3),
            eps                   NUMERIC(12, 4),
            book_value_ps         NUMERIC(12, 4),
            dividend_yield        NUMERIC(8, 4),
            dividend_per_share    NUMERIC(12, 4),
            dividend_payout_ratio NUMERIC(10, 3),
            market_cap            NUMERIC(18, 4),
            ev_sales              NUMERIC(10, 3),
            net_debt              NUMERIC(18, 4),
            net_debt_ebitda       NUMERIC(10, 3),
            asset_turnover        NUMERIC(10, 3),
            inventory_turnover    NUMERIC(10, 3),
            receivables_days      NUMERIC(10, 3),
            payable_days          NUMERIC(10, 3),
            cash_conv_cycle       NUMERIC(10, 3),
            fcf                   NUMERIC(18, 4),
            fcf_margin            NUMERIC(10, 3),
            fcf_yield             NUMERIC(10, 3),
            capex_to_revenue      NUMERIC(10, 3),
            capex_to_depreciation NUMERIC(10, 3),
            piotroski_f_score     INTEGER,
            altman_z_score        NUMERIC(10, 3),
            roic                  NUMERIC(10, 3),
            low_52w               NUMERIC(12, 4),
            high_52w              NUMERIC(12, 4),
            revenue_per_share     NUMERIC(12, 4),
            cfo_to_pat            NUMERIC(10, 3),
            computed_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            UNIQUE (stock_id, period_end, period_type)
        );
    """)
    op.execute("""
        CREATE INDEX ix_financial_ratios_stock_period
            ON financial_ratios (stock_id, period_end DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS financial_ratios CASCADE;")
