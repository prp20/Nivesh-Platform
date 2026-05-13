"""016 — detected_patterns table

Chart pattern signals detected by the scipy pattern engine.
pattern_type: e.g. 'golden_cross', 'death_cross', 'breakout', 'support', 'resistance'
direction: 'bullish' | 'bearish' | NULL

Revision ID: 016
Revises: 015
"""
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE detected_patterns (
            id             SERIAL       PRIMARY KEY,
            stock_id       INTEGER      NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
            pattern_type   VARCHAR(30)  NOT NULL,
            timeframe      VARCHAR(5)   NOT NULL,
            detected_on    DATE         NOT NULL,
            pattern_start  DATE         NOT NULL,
            pattern_end    DATE         NOT NULL,
            breakout_level NUMERIC(12, 4),
            direction      VARCHAR(10),
            confidence     NUMERIC(4, 3),
            is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
            metadata       JSONB,
            created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            UNIQUE (stock_id, pattern_type, detected_on)
        );
    """)
    op.execute("""
        CREATE INDEX idx_detected_patterns_active
            ON detected_patterns (stock_id, is_active, detected_on DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS detected_patterns CASCADE;")
