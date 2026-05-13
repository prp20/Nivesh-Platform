"""002 — admin_users table

Revision ID: 002
Revises: 001
"""
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
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


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admin_users CASCADE;")
