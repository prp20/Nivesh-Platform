"""017 — stock_ratings table

Composite rating per stock per day.
Populated by the rating engine (fundamental + valuation + technical + momentum + quality + shareholding).

Revision ID: 017
Revises: 016
"""
revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE stock_ratings (
            id                 SERIAL        PRIMARY KEY,
            stock_id           INTEGER       NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
            rated_on           DATE          NOT NULL,
            total_score        NUMERIC(6, 3),
            rating_label       VARCHAR(15),
            fundamental_score  NUMERIC(6, 3),
            valuation_score    NUMERIC(6, 3),
            technical_score    NUMERIC(6, 3),
            momentum_score     NUMERIC(6, 3),
            quality_score      NUMERIC(6, 3),
            shareholding_score NUMERIC(6, 3),
            score_breakdown    JSONB,
            UNIQUE (stock_id, rated_on)
        );
    """)
    op.execute("""
        CREATE INDEX idx_stock_ratings_stock_date ON stock_ratings (stock_id, rated_on DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS stock_ratings CASCADE;")
