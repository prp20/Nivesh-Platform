#!/usr/bin/env python3
"""
One-time script to create an admin user in the admin_users table.

Usage:
    cd nivesh-server
    python scripts/create_admin.py --username admin --password <your-password>

Requirements:
    - DATABASE_URL (Supabase direct URL, port 5432) must be set in .env
    - Run `alembic upgrade head` before running this script
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path so `app` is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models import AdminUser
from app.security import get_password_hash


async def create_admin(username: str, password: str) -> None:
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("ALEMBIC_URL")
    if not db_url:
        print("ERROR: DATABASE_URL or ALEMBIC_URL must be set.")
        sys.exit(1)

    # Ensure async driver prefix
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url, echo=False)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # Check if user already exists
        result = await session.execute(select(AdminUser).where(AdminUser.username == username))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"Admin user '{username}' already exists (id={existing.id}).")
            print("To update the password, delete the user and re-run this script.")
            await engine.dispose()
            return

        user = AdminUser(
            username=username,
            password_hash=get_password_hash(password),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        print(f"Admin user '{username}' created successfully (id={user.id}).")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Nivesh admin user")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Admin password (plaintext — hashed before storage)")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("ERROR: Password must be at least 8 characters.")
        sys.exit(1)

    asyncio.run(create_admin(args.username, args.password))


if __name__ == "__main__":
    main()
