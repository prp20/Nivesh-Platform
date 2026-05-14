"""
Rate limiting middleware for API endpoints.

Prevents abuse and DoS attacks by limiting requests per user/IP.
Uses in-memory storage (suitable for single-instance deployments).
For multi-instance deployments, consider Redis-based rate limiting.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

# Rate limit config: (requests_per_window, window_in_seconds)
RATE_LIMITS = {
    "/screener": (100, 60),  # 100 requests per minute
    "/stocks": (1000, 60),  # 1000 requests per minute
    "/stocks/search": (500, 60),  # 500 requests per minute
    "/pipeline": (50, 60),  # 50 admin requests per minute (strict for sensitive ops)
}

DEFAULT_LIMIT = (1000, 60)  # 1000 requests per minute for unlisted endpoints


class RateLimiter:
    """
    In-memory rate limiter using sliding window counter.

    Tracks (user_id, endpoint) tuples and enforces limits.
    Cleans up old entries periodically to prevent memory leak.
    """

    def __init__(self):
        # Format: {(user_id, endpoint): [(timestamp, count), ...]}
        self.requests: Dict[Tuple[str, str], list] = defaultdict(list)
        self.last_cleanup = datetime.now(timezone.utc)
        self._call_count = 0

    def is_allowed(self, user_id: str, endpoint: str) -> bool:
        """
        Check if request is allowed based on rate limit.

        Args:
            user_id: User identifier (username or IP)
            endpoint: API endpoint path (e.g., "/screener")

        Returns:
            True if request is allowed, False if rate-limited
        """
        # Get rate limit for this endpoint
        limit, window_secs = RATE_LIMITS.get(endpoint, DEFAULT_LIMIT)

        # Check if cleanup needed (every 1000 checks)
        self._call_count += 1
        if self._call_count % 1000 == 0:
            self._cleanup()


        key = (user_id, endpoint)
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=window_secs)

        # Remove old requests outside the window
        self.requests[key] = [
            (ts, cnt) for ts, cnt in self.requests[key] if ts > window_start
        ]

        # Count requests in current window
        request_count = sum(cnt for _, cnt in self.requests[key])

        if request_count >= limit:
            logger.warning(
                f"Rate limit exceeded for {user_id} on {endpoint} "
                f"({request_count}/{limit} in {window_secs}s)"
            )
            return False

        # Record this request
        if self.requests[key]:
            # Update the latest timestamp's count
            self.requests[key][-1] = (now, self.requests[key][-1][1] + 1)
        else:
            self.requests[key].append((now, 1))

        return True

    def _cleanup(self):
        """Remove old entries to prevent memory leak."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)  # Keep 1 hour of history

        # Remove keys with no recent requests
        keys_to_remove = []
        for key, entries in self.requests.items():
            # Keep only recent entries
            self.requests[key] = [(ts, cnt) for ts, cnt in entries if ts > cutoff]
            if not self.requests[key]:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.requests[key]

        self.last_cleanup = now
        logger.debug(f"Rate limiter cleanup: removed {len(keys_to_remove)} keys")


# Global rate limiter instance
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


def format_rate_limit_key(user_id: str) -> str:
    """
    Format a key for rate-limit headers.

    In production, use IP-based or JWT-based user identification.
    """
    return user_id or "anonymous"
