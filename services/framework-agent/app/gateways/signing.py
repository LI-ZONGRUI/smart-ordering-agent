"""Deterministic HMAC v1 signing for the uniCloud Framework Gateway."""

import hashlib
import hmac
import json
import re
import secrets
import time
from collections.abc import Callable, Mapping

SIGNATURE_VERSION = "v1"
CANONICAL_METHOD = "POST"
CANONICAL_PATH = "/framework-gateway"
NONCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")

Clock = Callable[[], int]
NonceFactory = Callable[[], str]


def encode_json_body(payload: Mapping[str, object]) -> bytes:
    """Encode once; these exact compact UTF-8 bytes are both signed and sent."""

    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_signing_string(*, timestamp: str, nonce: str, body_hash: str) -> str:
    return "\n".join(
        (SIGNATURE_VERSION, CANONICAL_METHOD, CANONICAL_PATH, timestamp, nonce, body_hash)
    )


def hmac_signature(*, secret: str, canonical: str) -> str:
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_nonce() -> str:
    """Generate 32 URL-safe characters, within the server's 16–64 character contract."""

    return secrets.token_urlsafe(24)


def unix_seconds() -> int:
    return int(time.time())


def build_auth_headers(
    body: bytes,
    *,
    secret: str,
    clock: Clock = unix_seconds,
    nonce_factory: NonceFactory = generate_nonce,
) -> dict[str, str]:
    timestamp_value = clock()
    nonce = nonce_factory()
    if (
        not isinstance(timestamp_value, int)
        or isinstance(timestamp_value, bool)
        or timestamp_value < 0
        or not isinstance(nonce, str)
        or NONCE_PATTERN.fullmatch(nonce) is None
        or not 32 <= len(secret) <= 256
    ):
        raise ValueError("invalid signing input")
    timestamp = str(timestamp_value)
    canonical = canonical_signing_string(
        timestamp=timestamp, nonce=nonce, body_hash=body_sha256(body)
    )
    return {
        "X-Framework-Signature-Version": SIGNATURE_VERSION,
        "X-Framework-Timestamp": timestamp,
        "X-Framework-Nonce": nonce,
        "X-Framework-Signature": hmac_signature(secret=secret, canonical=canonical),
    }
