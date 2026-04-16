import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

try:
    from backend.app.config import settings
    print(f"ADMIN_USERNAME: {settings.ADMIN_USERNAME}")
    print(f"ADMIN_PASSWORD_HASH: '{settings.ADMIN_PASSWORD_HASH}'")
    print(f"ENABLE_AUTH: {settings.ENABLE_AUTH}")
except Exception as e:
    print(f"Error loading settings: {e}")
