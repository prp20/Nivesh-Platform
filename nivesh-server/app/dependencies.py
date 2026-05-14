"""
FastAPI dependency re-exports.

Import from here for new code; routers can continue using
`security.get_current_user` directly for backward compatibility.
"""

from .security import get_current_user, require_admin

__all__ = ["get_current_user", "require_admin"]
