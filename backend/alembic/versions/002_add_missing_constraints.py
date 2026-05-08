"""add_missing_unique_constraints

Adds the missing unique constraint on financial_ratios that the pipeline
ON CONFLICT clause depends on. Tables were created via SQLAlchemy create_all
which was missing this constraint from the model definition.

Revision ID: 002
Revises: 001
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == 'sqlite':
        return
    # financial_ratios is missing its unique constraint.
    # The pipeline uses: ON CONFLICT (stock_id, period_end, period_type)
    # Use IF NOT EXISTS guard so this is safe to re-run.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'uq_financial_ratios_stock_period_type'
                  AND table_name = 'financial_ratios'
            ) THEN
                ALTER TABLE financial_ratios
                    ADD CONSTRAINT uq_financial_ratios_stock_period_type
                    UNIQUE (stock_id, period_end, period_type);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == 'sqlite':
        return
    op.execute("""
        ALTER TABLE financial_ratios
            DROP CONSTRAINT IF EXISTS uq_financial_ratios_stock_period_type;
    """)
