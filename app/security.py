import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "modernewolke2026!").strip()
SIGNING_SECRET = os.environ.get("SIGNING_SECRET", "modernewolke-oxygen-license-secret-key-32b").strip()
SESSION_EXPIRE_HOURS = int(os.environ.get("SESSION_EXPIRE_HOURS", "48"))

# In-memory active session tokens: token -> expiration timestamp
_ACTIVE_SESSIONS: dict[str, float] = {}


def verify_admin_password(password: str) -> bool:
    """Safely verify admin password."""
    return hmac.compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))


def create_session() -> str:
    """Create a new authenticated admin session token."""
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + (SESSION_EXPIRE_HOURS * 3600)
    _ACTIVE_SESSIONS[token] = expires_at
    return token


def validate_session(token: Optional[str]) -> bool:
    """Validate if session token is active and not expired."""
    if not token:
        return False
    expires_at = _ACTIVE_SESSIONS.get(token)
    if not expires_at:
        return False
    if time.time() > expires_at:
        _ACTIVE_SESSIONS.pop(token, None)
        return False
    return True


def invalidate_session(token: Optional[str]) -> None:
    if token:
        _ACTIVE_SESSIONS.pop(token, None)


def sign_license(
    license_key: str,
    instance_uuid: str,
    customer_name: str,
    valid_until: Optional[str],
    modules_str: str,
    timestamp: int,
) -> str:
    """Compute HMAC-SHA256 signature for verified license payload."""
    canonical = f"{license_key.upper().strip()}:{instance_uuid.lower().strip()}:{customer_name.strip()}:{valid_until or ''}:{modules_str}:{timestamp}"
    return hmac.new(SIGNING_SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_license_key() -> str:
    """Generate a clean, readable license key in format OXY-XXXX-XXXX-XXXX-XXXX."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # omit ambiguous O, 0, 1, I
    parts = []
    for _ in range(4):
        part = "".join(secrets.choice(alphabet) for _ in range(4))
        parts.append(part)
    return "OXY-" + "-".join(parts)
