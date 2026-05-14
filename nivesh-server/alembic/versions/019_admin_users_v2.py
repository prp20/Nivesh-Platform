"""019 — rebuild admin_users to match Phase 2 ORM model

The original admin_users table (migration 002) used a UUID PK, required an
email column, and stored the password in hashed_password. The Phase 2 ORM
model (AdminUser) was redesigned to use a BIGSERIAL PK, drop email/user_role,
and rename the column to password_hash. This migration reconciles the two.

Safe to drop-and-recreate: the table has no application data at this point
(admin users are created after deploy via scripts/create_admin.py).

Revision ID: 019
Revises: 018
"""
revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    # Drop the Phase 1 admin_users table (UUID PK, email, hashed_password, user_role).
    # No application data exists at this stage — admin users are seeded post-deploy.
    op.execute("DROP TABLE IF EXISTS admin_users CASCADE;")

    op.execute("""
        CREATE TABLE admin_users (
            id            BIGSERIAL    PRIMARY KEY,
            username      VARCHAR(50)  NOT NULL UNIQUE,
            password_hash TEXT         NOT NULL,
            is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE TRIGGER trg_admin_users_updated_at
            BEFORE UPDATE ON admin_users
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admin_users CASCADE;")

    # Restore Phase 1 schema
    op.execute("""
        CREATE TABLE admin_users (
            user_id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            username        VARCHAR(50)  NOT NULL UNIQUE,
            email           VARCHAR(255) NOT NULL UNIQUE,
            hashed_password VARCHAR(255) NOT NULL,
            user_role       VARCHAR(20)  NOT NULL DEFAULT 'analyst'
                                CHECK (user_role IN ('admin', 'analyst', 'service')),
            is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
            last_login_at   TIMESTAMPTZ,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_admin_users_role ON admin_users (user_role);")
    op.execute("""
        CREATE TRIGGER trg_admin_users_updated_at
            BEFORE UPDATE ON admin_users
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    op.execute("ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY "service_role_only" ON admin_users
            USING (auth.role() = 'service_role');
    """)
