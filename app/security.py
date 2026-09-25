import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from typing import Any, Optional

SIGNING_SECRET = os.environ.get("SIGNING_SECRET", "modernewolke-oxygen-license-secret-key-32b").strip()
SESSION_EXPIRE_HOURS = int(os.environ.get("SESSION_EXPIRE_HOURS", "48"))

# In-memory active session tokens: token -> {"expires_at": float, "user_id": int, "email": str}
_ACTIVE_SESSIONS: dict[str, dict[str, Any]] = {}


# ============================================================
# Password Hashing & Verification (PBKDF2-HMAC-SHA256)
# ============================================================

def hash_password(password: str) -> tuple[str, str]:
    """Generates a salt and PBKDF2-HMAC-SHA256 password hash."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        100_000,
    ).hex()
    return salt, pwd_hash


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    """Safely verifies password against stored salt and hash."""
    test_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        100_000,
    ).hex()
    return hmac.compare_digest(test_hash, password_hash)


# ============================================================
# TOTP (RFC 6238 Standard)
# ============================================================

def generate_totp_secret() -> str:
    """Generates a standard 20-byte Base32 secret string (32 characters, no padding)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8").replace("=", "")


def get_totp_code(secret: str, for_time: Optional[float] = None) -> str:
    """Computes standard 6-digit TOTP code for a timestamp according to RFC 6238."""
    if for_time is None:
        for_time = time.time()
    counter = int(for_time // 30)

    clean_secret = secret.strip().replace(" ", "").upper()
    padding_needed = (8 - len(clean_secret) % 8) % 8
    secret_bytes = base64.b32decode(clean_secret + "=" * padding_needed)

    msg = struct.pack(">Q", counter)
    digest = hmac.new(secret_bytes, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{code_int % 1_000_000:06d}"


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """
    Verifies a 6-digit TOTP code with time drift window.
    window=1 allows current 30s block, +/- 30 seconds.
    """
    clean_code = str(code).strip().replace(" ", "")
    if len(clean_code) != 6 or not clean_code.isdigit():
        return False

    now = time.time()
    for offset in range(-window, window + 1):
        test_time = now + (offset * 30)
        expected = get_totp_code(secret, test_time)
        if hmac.compare_digest(expected, clean_code):
            return True
    return False


def get_otpauth_url(secret: str, email: str, issuer: str = "Modernewolke") -> str:
    """Constructs standard otpauth URI for QR code generation."""
    clean_secret = secret.strip().replace(" ", "").upper()
    safe_email = email.strip()
    return f"otpauth://totp/{issuer}:{safe_email}?secret={clean_secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"


# ============================================================
# Session Management
# ============================================================

def create_session(user_id: int, email: str) -> str:
    """Creates a new authenticated session token."""
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + (SESSION_EXPIRE_HOURS * 3600)
    _ACTIVE_SESSIONS[token] = {
        "expires_at": expires_at,
        "user_id": user_id,
        "email": email.strip().lower(),
    }
    return token


def validate_session(token: Optional[str]) -> bool:
    """Checks if session token is active and valid."""
    if not token:
        return False
    session = _ACTIVE_SESSIONS.get(token)
    if not session:
        return False
    if time.time() > session["expires_at"]:
        _ACTIVE_SESSIONS.pop(token, None)
        return False
    return True


def get_session_user(token: Optional[str]) -> Optional[dict[str, Any]]:
    """Returns session info for token or None."""
    if not validate_session(token):
        return None
    return _ACTIVE_SESSIONS.get(token)


def invalidate_session(token: Optional[str]) -> None:
    if token:
        _ACTIVE_SESSIONS.pop(token, None)


# ============================================================
# License Signing & Keys
# ============================================================

def sign_license(
    license_key: str,
    instance_uuid: str,
    customer_name: str,
    valid_until: Optional[str],
    modules_str: str,
    timestamp: int,
) -> str:
    """Computes HMAC-SHA256 signature for verified license payload."""
    canonical = f"{license_key.upper().strip()}:{instance_uuid.lower().strip()}:{customer_name.strip()}:{valid_until or ''}:{modules_str}:{timestamp}"
    return hmac.new(SIGNING_SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_license_key() -> str:
    """Generates a clean, readable license key in format OXY-XXXX-XXXX-XXXX-XXXX."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    parts = []
    for _ in range(4):
        part = "".join(secrets.choice(alphabet) for _ in range(4))
        parts.append(part)
    return "OXY-" + "-".join(parts)
