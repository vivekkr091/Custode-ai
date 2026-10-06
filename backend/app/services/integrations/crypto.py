"""Cryptographic signing, verification, and secret management for CUSTODE Webhooks.

Implements:
1. High-entropy signing secret generation (cst_whsec_<public_id>_<secret>)
2. HMAC-SHA256 payload signing with timestamp replay protection
3. Constant-time signature verification (Stripe / GitHub webhook standard)
4. Configurable Secret Provider abstraction with documented encryption boundary
"""

from abc import ABC, abstractmethod
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict, Optional, Tuple, Union

from app.core.config import get_settings

SIGNING_SECRET_PREFIX = "cst_whsec_"
SIGNATURE_HEADER_NAME = "X-Custode-Signature"
DEFAULT_TOLERANCE_SECONDS = 300  # 5 minutes replay protection window


def generate_webhook_signing_secret() -> Tuple[str, str, str]:
    """Generate a high-entropy webhook signing secret.

    Format: cst_whsec_<12_hex_id>_<43_urlsafe_secret>
    Returns:
        (raw_secret, secret_prefix, secret_hash)
    """
    public_id = secrets.token_hex(6)  # 12 hex characters
    prefix = f"{SIGNING_SECRET_PREFIX}{public_id}"
    secret_part = secrets.token_urlsafe(32)
    raw_secret = f"{prefix}_{secret_part}"

    # Generate PBKDF2 hash for lookup/integrity verification
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        raw_secret.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    secret_hash = f"{salt}${dk.hex()}"

    return raw_secret, prefix, secret_hash


# ==============================================================================
# Secret Storage Provider Abstraction
# ==============================================================================

class BaseSecretProvider(ABC):
    """Abstract boundary for managing sensitive webhook signing secrets at rest."""

    @abstractmethod
    def encrypt(self, raw_secret: str) -> str:
        """Encrypt or wrap a signing secret before database persistence."""
        pass

    @abstractmethod
    def decrypt(self, stored_ciphertext: str) -> str:
        """Decrypt or unwrap a signing secret for cryptographic HMAC dispatch."""
        pass


class LocalAppKeySecretProvider(BaseSecretProvider):
    """Application-level secret provider using SECRET_KEY key derivation.

    SECURITY & LIMITATION NOTICE:
    This provider derives an authenticated envelope using HMAC-SHA256 and salt
    from the application's configured SECRET_KEY. In enterprise high-assurance
    production environments, configure a Hardware Security Module (HSM) or
    cloud Key Management Service (AWS KMS, GCP KMS, Azure Key Vault, HashiCorp Vault)
    by implementing a dedicated KMSSecretProvider.
    """

    def __init__(self, master_key: Optional[str] = None) -> None:
        settings = get_settings()
        self._master_key = (master_key or settings.SECRET_KEY).encode("utf-8")

    def _derive_key(self, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", self._master_key, salt, 50_000)

    def encrypt(self, raw_secret: str) -> str:
        salt = secrets.token_bytes(16)
        derived_key = self._derive_key(salt)
        
        # Authenticated envelope: tag = HMAC-SHA256(derived_key, raw_secret)
        raw_bytes = raw_secret.encode("utf-8")
        tag = hmac.new(derived_key, raw_bytes, hashlib.sha256).digest()
        
        # Reversible envelope with key derivation
        # Mask using derived stream
        stream = hashlib.sha256(derived_key + salt).digest()
        while len(stream) < len(raw_bytes):
            stream += hashlib.sha256(stream + derived_key).digest()
        
        cipher_bytes = bytes(b ^ s for b, s in zip(raw_bytes, stream[:len(raw_bytes)]))
        payload = salt + tag + cipher_bytes
        return f"custode_enc_v1:{base64.urlsafe_b64encode(payload).decode('ascii')}"

    def decrypt(self, stored_ciphertext: str) -> str:
        if not stored_ciphertext.startswith("custode_enc_v1:"):
            raise ValueError("Unsupported or corrupted secret envelope version")
        
        raw_b64 = stored_ciphertext.split(":", 1)[1]
        data = base64.urlsafe_b64decode(raw_b64.encode("ascii"))
        
        if len(data) < 48:  # 16 salt + 32 tag + min 0 payload
            raise ValueError("Corrupted secret envelope")
        
        salt = data[:16]
        expected_tag = data[16:48]
        cipher_bytes = data[48:]
        
        derived_key = self._derive_key(salt)
        stream = hashlib.sha256(derived_key + salt).digest()
        while len(stream) < len(cipher_bytes):
            stream += hashlib.sha256(stream + derived_key).digest()
        
        raw_bytes = bytes(b ^ s for b, s in zip(cipher_bytes, stream[:len(cipher_bytes)]))
        actual_tag = hmac.new(derived_key, raw_bytes, hashlib.sha256).digest()
        
        if not hmac.compare_digest(actual_tag, expected_tag):
            raise ValueError("Secret integrity verification failed: envelope tag mismatch")
        
        return raw_bytes.decode("utf-8")


_default_secret_provider: Optional[BaseSecretProvider] = None


def get_secret_provider() -> BaseSecretProvider:
    """Retrieve the active secret storage provider instance."""
    global _default_secret_provider
    if _default_secret_provider is None:
        _default_secret_provider = LocalAppKeySecretProvider()
    return _default_secret_provider


def set_secret_provider(provider: BaseSecretProvider) -> None:
    """Configure a custom or KMS secret storage provider."""
    global _default_secret_provider
    _default_secret_provider = provider


# ==============================================================================
# Webhook HMAC-SHA256 Signing & Verification
# ==============================================================================

def compute_webhook_signature(
    payload: Union[bytes, str, Dict[str, Any]],
    secret: str,
    timestamp: Optional[int] = None,
) -> Tuple[str, str]:
    """Compute HMAC-SHA256 webhook signature with timestamp.

    Canonical signature payload format:
    t=<timestamp>.<serialized_json_or_body>

    Returns:
        (header_value, raw_hex_signature)
        e.g. ("t=1727780000,v1=5d41402abc...", "5d41402abc...")
    """
    if timestamp is None:
        timestamp = int(time.time())

    if isinstance(payload, bytes):
        payload_str = payload.decode("utf-8")
    elif isinstance(payload, dict):
        payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    else:
        payload_str = str(payload)

    canonical_data = f"t={timestamp}.{payload_str}".encode("utf-8")
    signature = hmac.new(
        secret.encode("utf-8"),
        canonical_data,
        hashlib.sha256,
    ).hexdigest()

    header_value = f"t={timestamp},v1={signature}"
    return header_value, signature


def verify_webhook_signature(
    payload: Union[bytes, str, Dict[str, Any]],
    signature_header: str,
    secret: str,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
) -> bool:
    """Verify an incoming webhook signature using constant-time comparison and replay defense.

    Header format: t=<timestamp>,v1=<sig>
    """
    if not signature_header or not secret:
        return False

    parts = dict(item.strip().split("=", 1) for item in signature_header.split(",") if "=" in item)
    t_str = parts.get("t")
    v1_sig = parts.get("v1")

    if not t_str or not v1_sig:
        return False

    try:
        timestamp = int(t_str)
    except ValueError:
        return False

    # Replay protection: check timestamp against current time (max drift in past, max 60s in future)
    now = int(time.time())
    if (now - timestamp) > tolerance_seconds or (timestamp - now) > 60:
        return False

    # Compute expected signature using identical timestamp
    _, expected_sig = compute_webhook_signature(payload, secret, timestamp=timestamp)

    # Constant-time comparison
    return hmac.compare_digest(v1_sig, expected_sig)
