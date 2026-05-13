"""001 — base extensions and shared trigger function

Revision ID: 001
Revises: (none — first migration)
"""
revision = "001"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;")
    # Extensions are intentionally not dropped — they may be shared
