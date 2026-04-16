"""
Admin credential setup helper — called by all platform setup scripts.

Usage: python3 setup/admin_helper.py <path-to-backend-.env>

Prompts for admin username + password, bcrypt-hashes the password,
and writes ADMIN_USERNAME + ADMIN_PASSWORD_HASH into the backend .env file.
"""
import sys
import re
import getpass

try:
    import bcrypt as _bcrypt
except ImportError:
    print("[ERROR] bcrypt not installed. Run: pip install bcrypt>=3.2.0")
    sys.exit(1)

if len(sys.argv) < 2:
    print("[ERROR] Usage: python3 admin_helper.py <path-to-backend-.env>")
    sys.exit(1)

env_file = sys.argv[1]

try:
    content = open(env_file).read()
except FileNotFoundError:
    print(f"[ERROR] .env file not found: {env_file}")
    sys.exit(1)

username = input("  Admin username [admin]: ").strip() or "admin"

while True:
    pw = getpass.getpass("  Admin password: ")
    if not pw:
        print("  [WARN] Password cannot be empty.")
        continue
    pw2 = getpass.getpass("  Confirm password: ")
    if pw != pw2:
        print("  [WARN] Passwords do not match. Try again.")
        continue
    break

hash_ = _bcrypt.hashpw(pw.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
content = re.sub(r"ADMIN_USERNAME=.*", f"ADMIN_USERNAME={username}", content)
content = re.sub(r"ADMIN_PASSWORD_HASH=.*", f"ADMIN_PASSWORD_HASH={hash_}", content)
open(env_file, "w").write(content)
print(f"[OK]    Admin credentials saved (username: {username})")
