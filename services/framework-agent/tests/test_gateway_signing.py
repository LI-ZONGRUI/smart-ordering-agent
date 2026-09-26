import re

import pytest

from app.gateways.signing import (
    CANONICAL_PATH,
    NONCE_PATTERN,
    body_sha256,
    build_auth_headers,
    canonical_signing_string,
    encode_json_body,
    generate_nonce,
    hmac_signature,
)

SECRET = "test-only-framework-secret-at-least-32-chars"
TIMESTAMP = 1_700_000_000
NONCE = "test_nonce_1234567890"


def test_python_hmac_v1_golden_vector_matches_protocol() -> None:
    body = encode_json_body({"operation": "search_menu", "arguments": {"query": "柠檬茶"}})
    assert body == '{"operation":"search_menu","arguments":{"query":"柠檬茶"}}'.encode()
    assert body_sha256(body) == "b6994a5444a2894a6d5e18cafd33a49aff8679a46a190d59c8b30c5dc5740b38"
    canonical = canonical_signing_string(
        timestamp=str(TIMESTAMP), nonce=NONCE, body_hash=body_sha256(body)
    )
    assert canonical == (
        "v1\nPOST\n/framework-gateway\n1700000000\ntest_nonce_1234567890\n"
        "b6994a5444a2894a6d5e18cafd33a49aff8679a46a190d59c8b30c5dc5740b38"
    )
    assert hmac_signature(secret=SECRET, canonical=canonical) == (
        "e2f706dc79cae27caf343328febf6841a803a4cfd736a83233efc39e74c0cafd"
    )


def _signature(
    *,
    operation: str = "search_menu",
    arguments: dict[str, object] | None = None,
    timestamp: int = TIMESTAMP,
    nonce: str = NONCE,
    path: str = CANONICAL_PATH,
) -> str:
    body = encode_json_body({"operation": operation, "arguments": arguments or {"query": "柠檬茶"}})
    canonical = "\n".join(("v1", "POST", path, str(timestamp), nonce, body_sha256(body)))
    return hmac_signature(secret=SECRET, canonical=canonical)


@pytest.mark.parametrize(
    "change",
    [
        {"operation": "list_available_drinks", "arguments": {}},
        {"arguments": {"query": "可乐"}},
        {"timestamp": TIMESTAMP + 1},
        {"nonce": "other_nonce_123456789"},
        {"path": "/other"},
    ],
)
def test_each_signed_component_changes_signature(change: dict[str, object]) -> None:
    assert _signature(**change) != _signature()


def test_body_byte_change_changes_signature() -> None:
    compact = encode_json_body({"operation": "list_available_drinks", "arguments": {}})
    spaced = b'{"operation": "list_available_drinks", "arguments": {}}'
    first = build_auth_headers(
        compact, secret=SECRET, clock=lambda: TIMESTAMP, nonce_factory=lambda: NONCE
    )
    second = build_auth_headers(
        spaced, secret=SECRET, clock=lambda: TIMESTAMP, nonce_factory=lambda: NONCE
    )
    assert first["X-Framework-Signature"] != second["X-Framework-Signature"]


def test_generated_nonce_is_cryptographically_random_contract_shape() -> None:
    values = {generate_nonce() for _ in range(20)}
    assert len(values) == 20
    assert all(16 <= len(value) <= 64 and NONCE_PATTERN.fullmatch(value) for value in values)


@pytest.mark.parametrize("nonce", ["short", "contains space 123", "x" * 65])
def test_invalid_nonce_is_rejected(nonce: str) -> None:
    with pytest.raises(ValueError, match="invalid signing input"):
        build_auth_headers(
            b"{}", secret=SECRET, clock=lambda: TIMESTAMP, nonce_factory=lambda: nonce
        )


def test_auth_headers_have_exact_protocol_material_without_secret() -> None:
    headers = build_auth_headers(
        b"{}", secret=SECRET, clock=lambda: TIMESTAMP, nonce_factory=lambda: NONCE
    )
    assert set(headers) == {
        "X-Framework-Signature-Version",
        "X-Framework-Timestamp",
        "X-Framework-Nonce",
        "X-Framework-Signature",
    }
    assert headers["X-Framework-Signature-Version"] == "v1"
    assert re.fullmatch(r"[a-f0-9]{64}", headers["X-Framework-Signature"])
    assert SECRET not in str(headers)
