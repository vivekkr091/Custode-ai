"""Cryptographic utilities for API keys, passwords, and JWT access tokens.

Implements:
1. Agent API key generation, hashing, and constant-time verification (Milestone 4).
2. Industry-standard password hashing and verification using PBKDF2-HMAC-SHA256 (Milestone 14).
3. RFC 7519 / RFC 7515 compliant HS256 JWT access token creation and constant-time validation.
"""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from typing import Any, Dict, Optional, Tuple

from app.core.config import get_settings

# --- Agent Key Constants ---
API_KEY_PREFIX = "cst_ag_"
PBKDF2_KEY_ITERATIONS = 100_000

# --- Password Hash Constants ---
PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000  # OWASP recommendation for PBKDF2-HMAC-SHA256


class TokenError(Exception):
    """Base exception for JWT processing failures."""
    pass


class TokenExpiredError(TokenError):
    """Raised when token expiration timestamp is in the past."""
    pass


class InvalidTokenError(TokenError):
    """Raised when token signature, format, or claims are invalid."""
    pass


# ==============================================================================
# 1. Agent API Key Cryptography (Milestone 4)
# ==============================================================================

def generate_agent_api_key() -> Tuple[str, str]:
    """Generate a high-entropy agent API key and its indexed lookup prefix.

    Format: cst_ag_<10_hex_id>_<43_urlsafe_secret>
    Returns:
        (raw_api_key, credential_prefix)
    """
    public_id = secrets.token_hex(5)  # 10 hex characters
    prefix = f"{API_KEY_PREFIX}{public_id}"
    secret_part = secrets.token_urlsafe(32)
    raw_key = f"{prefix}_{secret_part}"
    return raw_key, prefix


def extract_prefix_from_key(raw_key: str) -> Optional[str]:
    """Extract the lookup prefix from a presented API key, or None if invalid format."""
    trimmed = raw_key.strip()
    if not trimmed.startswith(API_KEY_PREFIX):
        return None
    parts = trimmed.split("_")
    if len(parts) < 4:
        return None
    prefix = f"{parts[0]}_{parts[1]}_{parts[2]}"
    return prefix


def hash_api_key(raw_key: str) -> str:
    """Hash an API key using PBKDF2-HMAC-SHA256 with a unique random salt."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        raw_key.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_KEY_ITERATIONS,
    )
    return f"{salt}${dk.hex()}"


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Verify a raw API key against a stored salted hash using constant-time comparison."""
    try:
        salt, expected_dk_hex = stored_hash.split("$", 1)
        actual_dk = hashlib.pbkdf2_hmac(
            "sha256",
            raw_key.encode("utf-8"),
            salt.encode("utf-8"),
            PBKDF2_KEY_ITERATIONS,
        )
        return hmac.compare_digest(actual_dk.hex(), expected_dk_hex)
    except Exception:
        return False


# ==============================================================================
# 2. Human Password Cryptography (Milestone 14)
# ==============================================================================

def hash_password(password: str) -> str:
    """Hash a user password using PBKDF2-HMAC-SHA256 with 600,000 iterations and 16-byte salt."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"{PASSWORD_HASH_PREFIX}${PASSWORD_ITERATIONS}${salt}${dk.hex()}"


def verify_password(plain_password: str, stored_hash: Optional[str]) -> bool:
    """Verify a plaintext password against the stored password hash in constant time."""
    if not stored_hash:
        return False
    try:
        parts = stored_hash.split("$")
        if len(parts) != 4 or parts[0] != PASSWORD_HASH_PREFIX:
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_dk_hex = parts[3]

        actual_dk = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return hmac.compare_digest(actual_dk.hex(), expected_dk_hex)
    except Exception:
        return False


# ==============================================================================
# 3. RFC 7519 / RFC 7515 HS256 JWT Implementation (Milestone 14)
# ==============================================================================

def _base64url_encode(data: bytes) -> str:
    """Encode bytes to base64url string without trailing padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(data_str: str) -> bytes:
    """Decode base64url string with flexible padding support."""
    rem = len(data_str) % 4
    if rem > 0:
        data_str += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data_str.encode("ascii"))


def create_access_token(
    subject: str,
    claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, int]:
    """Create a cryptographically signed HS256 JWT access token.

    Returns:
        (token_string, expires_in_seconds)
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
        expires_in = int(expires_delta.total_seconds())
    else:
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        expire = now + timedelta(seconds=expires_in)

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.AUTH_ISSUER,
        "aud": settings.AUTH_AUDIENCE,
    }
    if claims:
        payload.update(claims)

    header = {
        "alg": settings.AUTH_ALGORITHM,
        "typ": "JWT",
    }

    header_bytes = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    header_b64 = _base64url_encode(header_bytes)
    payload_b64 = _base64url_encode(payload_bytes)

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    secret_key = settings.AUTH_SECRET_KEY.encode("utf-8")

    signature = hmac.new(secret_key, signing_input, hashlib.sha256).digest()
    sig_b64 = _base64url_encode(signature)

    token = f"{header_b64}.{payload_b64}.{sig_b64}"
    return token, expires_in


def decode_access_token(token: str) -> Dict[str, Any]:
    """Verify and decode an HS256 JWT access token.

    Raises:
        TokenExpiredError: If the expiration timestamp has passed.
        InvalidTokenError: If signature, header, or payload format is invalid.
    """
    settings = get_settings()
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise InvalidTokenError("Invalid token format")

    header_b64, payload_b64, sig_b64 = parts

    # 1. Verify signature in constant time
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    secret_key = settings.AUTH_SECRET_KEY.encode("utf-8")
    expected_sig = hmac.new(secret_key, signing_input, hashlib.sha256).digest()
    expected_sig_b64 = _base64url_encode(expected_sig)

    if not hmac.compare_digest(sig_b64, expected_sig_b64):
        raise InvalidTokenError("Invalid token signature")

    # 2. Decode header and verify algorithm
    try:
        header_bytes = _base64url_decode(header_b64)
        header = json.loads(header_bytes.decode("utf-8"))
        if header.get("alg") != settings.AUTH_ALGORITHM:
            raise InvalidTokenError(f"Unsupported algorithm '{header.get('alg')}'")
        if header.get("typ") != "JWT":
            raise InvalidTokenError("Invalid token type")
    except Exception as e:
        if isinstance(e, InvalidTokenError):
            raise
        raise InvalidTokenError("Corrupt token header")

    # 3. Decode payload
    try:
        payload_bytes = _base64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise InvalidTokenError("Corrupt token payload")

    # 4. Check expiration
    exp = payload.get("exp")
    if exp is not None:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if now_ts > exp:
            raise TokenExpiredError("Token has expired")

    # 5. Check issuer and audience if configured
    if settings.AUTH_ISSUER and payload.get("iss") != settings.AUTH_ISSUER:
        raise InvalidTokenError("Invalid token issuer")
    if settings.AUTH_AUDIENCE and payload.get("aud") != settings.AUTH_AUDIENCE:
        raise InvalidTokenError("Invalid token audience")

    return payload
