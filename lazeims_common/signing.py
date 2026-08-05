"""Ed25519 asymmetric package signing.

Central keeps the private key; Station releases contain only the public
verification key. This is used for the canonical ``station-package/v1``
manifest so the Station can verify signatures without any shared secret.

Key management:
    * Production: ``PACKAGE_SIGNING_PRIVATE_KEY_PATH`` env var points to a
      PEM-encoded Ed25519 private key on disk. Never committed to git.
    * Development/test: a deterministic test keypair is generated from a fixed
      seed so tests are reproducible without external files.
    * The public key is embedded in Station releases as a PEM file or base64
      constant — it is NOT secret.
"""

from __future__ import annotations

import os
from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .hashing import canonical_bytes


# ── Key loading ──────────────────────────────────────────────────────────────

# Deterministic test seed (NOT secret; for reproducible dev/test only).
_TEST_SEED = b"lazeims-dev-test-signing-key-00!"  # exactly 32 bytes


def _load_private_key_from_path(path: str) -> Ed25519PrivateKey:
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)  # type: ignore[return-value]


def generate_test_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Generate a deterministic test keypair from a fixed seed.

    ONLY for development and automated tests. Production MUST use a real
    generated key stored securely on disk.
    """
    private_key = Ed25519PrivateKey.from_private_bytes(_TEST_SEED)
    return private_key, private_key.public_key()


@lru_cache(maxsize=1)
def get_signing_private_key() -> Ed25519PrivateKey:
    """Load the signing private key.

    Checks ``PACKAGE_SIGNING_PRIVATE_KEY_PATH`` first (production path).
    Falls back to the deterministic test key when the env var is unset or empty,
    which is acceptable only in development/test environments.
    """
    path = os.environ.get("PACKAGE_SIGNING_PRIVATE_KEY_PATH", "").strip()
    if path:
        return _load_private_key_from_path(path)
    return generate_test_keypair()[0]


@lru_cache(maxsize=1)
def get_signing_public_key() -> Ed25519PublicKey:
    """Get the public verification key (derived from the loaded private key)."""
    return get_signing_private_key().public_key()


def get_public_key_pem() -> str:
    """Return the public key in PEM format (for embedding in Station releases)."""
    return get_signing_public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def load_public_key_from_pem(pem_data: str | bytes) -> Ed25519PublicKey:
    """Load a public key from PEM (used by Station to verify packages)."""
    if isinstance(pem_data, str):
        pem_data = pem_data.encode("ascii")
    return serialization.load_pem_public_key(pem_data)  # type: ignore[return-value]


# ── Signing and verification ─────────────────────────────────────────────────

def sign_data(data: dict) -> str:
    """Sign the canonical JSON of ``data`` with Ed25519. Returns hex signature."""
    private_key = get_signing_private_key()
    payload = canonical_bytes(data)
    signature = private_key.sign(payload)
    return signature.hex()


def verify_signature(data: dict, signature_hex: str, public_key: Ed25519PublicKey | None = None) -> bool:
    """Verify an Ed25519 signature against canonical JSON of ``data``.

    Uses the configured public key by default, or an explicit one if provided
    (e.g. Station loading from its embedded PEM).
    """
    if public_key is None:
        public_key = get_signing_public_key()
    try:
        payload = canonical_bytes(data)
        signature = bytes.fromhex(signature_hex)
        public_key.verify(signature, payload)
        return True
    except Exception:
        return False


def sign_package_manifest(manifest: dict) -> str:
    """Sign a package manifest, returning the ``ed25519:<hex>`` prefixed string."""
    raw_hex = sign_data(manifest)
    return f"ed25519:{raw_hex}"


def verify_package_signature(manifest: dict, signature: str, public_key: Ed25519PublicKey | None = None) -> bool:
    """Verify a package signature (expects ``ed25519:<hex>`` prefix)."""
    if not signature.startswith("ed25519:"):
        return False
    hex_sig = signature[len("ed25519:"):]
    return verify_signature(manifest, hex_sig, public_key)


def sign_provision_request(payload: dict) -> str:
    """Sign a provisioning request payload, returning ``ed25519:<hex>``.

    Used by lazeims-core when calling backend-sis's provisioning endpoint so
    the request is authenticated without a shared secret in ``.env``.
    """
    raw_hex = sign_data(payload)
    return f"ed25519:{raw_hex}"


def verify_provision_signature(
    payload: dict, signature: str, public_key: Ed25519PublicKey | None = None
) -> bool:
    """Verify a provisioning request signature (expects ``ed25519:<hex>`` prefix).

    Used by backend-sis to authenticate provisioning requests from lazeims-core
    without requiring a shared secret environment variable.
    """
    if not signature.startswith("ed25519:"):
        return False
    hex_sig = signature[len("ed25519:"):]
    return verify_signature(payload, hex_sig, public_key)
