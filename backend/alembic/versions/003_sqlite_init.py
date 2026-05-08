"""sqlite_init

Creates all tables for fresh SQLite installs. For PostgreSQL this is a no-op
because migrations 001 and 002 already handle schema creation.

Revision ID: 003
Revises: 002
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = 'e7b9d9f1a2c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != 'sqlite':
        # PostgreSQL already handled by 001/002
        return

    # Import all models to ensure they are registered with Base before create_all
    import sys, os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
    from app.database import Base
    import app.models  # noqa: F401 — registers all ORM models with Base

    Base.metadata.create_all(bind=connection)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != 'sqlite':
        return

    import sys, os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
    from app.database import Base
    import app.models  # noqa: F401

    Base.metadata.drop_all(bind=connection)
