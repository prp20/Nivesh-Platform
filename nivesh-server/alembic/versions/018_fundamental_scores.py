"""018 — fundamental_scores table

LangGraph-computed fundamental scores per (stock, period_end, score_version).
Scores are broken down by P&L, Balance Sheet, and Cash Flow sub-components.

Revision ID: 018
Revises: 017
"""
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fundamental_scores (
            id                          SERIAL       PRIMARY KEY,
            stock_id                    INTEGER      NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
            period_end                  DATE         NOT NULL,
            period_type                 VARCHAR(10)  NOT NULL,
            score_version               VARCHAR(10)  NOT NULL DEFAULT 'v1.0',
            pl_score                    NUMERIC(6, 3),
            bs_score                    NUMERIC(6, 3),
            cf_score                    NUMERIC(6, 3),
            pl_growth_score             NUMERIC(6, 3),
            pl_margin_score             NUMERIC(6, 3),
            pl_eps_score                NUMERIC(6, 3),
            pl_consistency_score        NUMERIC(6, 3),
            bs_leverage_score           NUMERIC(6, 3),
            bs_liquidity_score          NUMERIC(6, 3),
            bs_asset_score              NUMERIC(6, 3),
            bs_networth_score           NUMERIC(6, 3),
            cf_operating_score          NUMERIC(6, 3),
            cf_capex_score              NUMERIC(6, 3),
            cf_financing_score          NUMERIC(6, 3),
            composite_fundamental_score NUMERIC(6, 3),
            reasoning_label             VARCHAR(50),
            reasoning_text              TEXT,
            computed_at                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            UNIQUE (stock_id, period_end, score_version)
        );
    """)
    op.execute("""
        CREATE INDEX ix_fundamental_scores_stock_id ON fundamental_scores (stock_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fundamental_scores CASCADE;")
