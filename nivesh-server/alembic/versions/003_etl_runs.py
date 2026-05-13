"""003 — etl_runs table (replaces sync_jobs + pipeline_audit)

Unified ETL job tracking table for all ingestion pipelines.
entity_id = scheme_code for MF jobs, symbol for stock jobs, NULL for market-wide.

BLOCKER NOTE: App code in crud.py and routers/sync.py still references sync_jobs.
Those references must be updated to etl_runs in a later phase before
sync_jobs / pipeline_audit can be dropped from the old monolith.
See BLOCKERS.md for details.

Revision ID: 003
Revises: 002
"""
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE etl_runs (
            id            BIGSERIAL    PRIMARY KEY,
            pipeline_name VARCHAR(60)  NOT NULL,
            entity_id     VARCHAR(50),
            status        VARCHAR(10)  NOT NULL DEFAULT 'RUNNING'
                              CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED', 'PARTIAL')),
            triggered_by  VARCHAR(20)  NOT NULL DEFAULT 'scheduler'
                              CHECK (triggered_by IN ('scheduler', 'manual', 'backfill')),
            started_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            ended_at      TIMESTAMPTZ,
            records_in    INTEGER      NOT NULL DEFAULT 0,
            records_out   INTEGER      NOT NULL DEFAULT 0,
            error_msg     TEXT,
            metadata      JSONB
        );
    """)
    # Prevents two concurrent RUNNING jobs for the same pipeline + entity
    op.execute("""
        CREATE UNIQUE INDEX uq_etl_runs_running
            ON etl_runs (pipeline_name, COALESCE(entity_id, ''))
            WHERE status = 'RUNNING';
    """)
    op.execute("""
        CREATE INDEX idx_etl_runs_pipeline_started
            ON etl_runs (pipeline_name, started_at DESC);
    """)
    op.execute("""
        CREATE INDEX idx_etl_runs_status
            ON etl_runs (status, started_at DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS etl_runs CASCADE;")
