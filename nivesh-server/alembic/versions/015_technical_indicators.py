"""015 — technical_indicators table

Pre-computed daily indicators per (stock, date, timeframe).
Populated by the TA-Lib pipeline job after each price ingestion run.
timeframe: '1d' | '1w'

Revision ID: 015
Revises: 014
"""
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE technical_indicators (
            id                BIGSERIAL     PRIMARY KEY,
            stock_id          INTEGER       NOT NULL REFERENCES stocks (id) ON DELETE CASCADE,
            ind_date          DATE          NOT NULL,
            timeframe         VARCHAR(5)    NOT NULL,
            sma_20            NUMERIC(12, 4),
            sma_50            NUMERIC(12, 4),
            sma_200           NUMERIC(12, 4),
            ema_9             NUMERIC(12, 4),
            ema_21            NUMERIC(12, 4),
            ema_50            NUMERIC(12, 4),
            rsi_14            NUMERIC(8, 4),
            macd_line         NUMERIC(12, 4),
            macd_signal       NUMERIC(12, 4),
            macd_hist         NUMERIC(12, 4),
            bb_upper          NUMERIC(12, 4),
            bb_middle         NUMERIC(12, 4),
            bb_lower          NUMERIC(12, 4),
            atr_14            NUMERIC(12, 4),
            adx_14            NUMERIC(8, 4),
            stoch_k           NUMERIC(8, 4),
            stoch_d           NUMERIC(8, 4),
            volume_sma_20     BIGINT,
            volume_sma_50     BIGINT,
            volume_ratio      NUMERIC(10, 3),
            obv               BIGINT,
            vwap_20           NUMERIC(12, 4),
            cci_20            NUMERIC(10, 3),
            williams_r        NUMERIC(10, 3),
            roc_14            NUMERIC(10, 3),
            beta_1y           NUMERIC(10, 4),
            rs_6m_vs_nifty    NUMERIC(10, 3),
            pct_from_52w_high NUMERIC(10, 3),
            pct_from_52w_low  NUMERIC(10, 3),
            UNIQUE (stock_id, ind_date, timeframe)
        );
    """)
    op.execute("""
        CREATE INDEX ix_technical_indicator_stock_date
            ON technical_indicators (stock_id, ind_date DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS technical_indicators CASCADE;")
