"""Tests for Ed25519 provisioning request signing and verification.

These tests cover sign_provision_request() and verify_provision_signature(),
the server-to-server authentication functions used when lazeims-core calls
backend-sis's provisioning endpoint.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from lazeims_common.signing import (
    generate_test_keypair,
    get_public_key_pem,
    load_public_key_from_pem,
    sign_provision_request,
    verify_provision_signature,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_PROVISION_PAYLOAD = {
    "external_exam_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "exam_name": "CSEE 2026",
    "exam_level": "FTNA",
    "partner_label": "LAZEIMS",
    "scopes": [
        "collection:push",
        "results:process",
        "results:read",
        "results:download",
    ],
    "requested_by": {
        "username": "admin",
        "name": "System Admin",
        "role": "SUPER_ADMIN",
    },
}

MINIMAL_PAYLOAD = {"external_exam_id": "test-123", "exam_name": "Test"}

NESTED_PAYLOAD = {
    "external_exam_id": "nested-001",
    "exam_name": "Nested Test",
    "metadata": {
        "subjects": [
            {"code": "011", "name": "Kiswahili"},
            {"code": "012", "name": "English"},
        ],
        "counts": {"schools": 5, "candidates": 200},
    },
}


# ── sign_provision_request ───────────────────────────────────────────────────


class TestSignProvisionRequest:
    """sign_provision_request() produces valid ed25519-prefixed signatures."""

    def test_returns_ed25519_prefixed_string(self):
        sig = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        assert sig.startswith("ed25519:")
        # The hex portion should be 128 characters (64 bytes as hex)
        hex_part = sig[len("ed25519:"):]
        assert len(hex_part) == 128
        # Verify it is valid hex
        bytes.fromhex(hex_part)

    def test_deterministic_for_same_payload(self):
        sig1 = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        sig2 = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        assert sig1 == sig2

    def test_different_payloads_produce_different_signatures(self):
        sig1 = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        sig2 = sign_provision_request(MINIMAL_PAYLOAD)
        assert sig1 != sig2

    def test_works_with_minimal_payload(self):
        sig = sign_provision_request(MINIMAL_PAYLOAD)
        assert sig.startswith("ed25519:")

    def test_works_with_nested_payload(self):
        sig = sign_provision_request(NESTED_PAYLOAD)
        assert sig.startswith("ed25519:")


# ── verify_provision_signature ───────────────────────────────────────────────


class TestVerifyProvisionSignature:
    """verify_provision_signature() correctly validates or rejects signatures."""

    def test_valid_signature_verifies(self):
        sig = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        assert verify_provision_signature(SAMPLE_PROVISION_PAYLOAD, sig) is True

    def test_valid_signature_with_explicit_public_key(self):
        _, pub = generate_test_keypair()
        sig = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        assert verify_provision_signature(SAMPLE_PROVISION_PAYLOAD, sig, public_key=pub) is True

    def test_valid_signature_with_pem_loaded_key(self):
        pem = get_public_key_pem()
        pub = load_public_key_from_pem(pem)
        sig = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        assert verify_provision_signature(SAMPLE_PROVISION_PAYLOAD, sig, public_key=pub) is True

    def test_tampered_payload_rejects(self):
        sig = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        tampered = dict(SAMPLE_PROVISION_PAYLOAD)
        tampered["exam_name"] = "TAMPERED"
        assert verify_provision_signature(tampered, sig) is False

    def test_extra_field_in_payload_rejects(self):
        sig = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        tampered = dict(SAMPLE_PROVISION_PAYLOAD)
        tampered["injected_field"] = "malicious"
        assert verify_provision_signature(tampered, sig) is False

    def test_removed_field_from_payload_rejects(self):
        sig = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        tampered = {k: v for k, v in SAMPLE_PROVISION_PAYLOAD.items() if k != "exam_level"}
        assert verify_provision_signature(tampered, sig) is False

    def test_wrong_public_key_rejects(self):
        other_private = Ed25519PrivateKey.generate()
        other_pub = other_private.public_key()
        sig = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        assert verify_provision_signature(SAMPLE_PROVISION_PAYLOAD, sig, public_key=other_pub) is False

    def test_invalid_signature_hex_rejects(self):
        assert verify_provision_signature(SAMPLE_PROVISION_PAYLOAD, "ed25519:not-valid-hex") is False

    def test_wrong_prefix_rejects(self):
        sig = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        # Replace prefix with something else
        bad_sig = "hmac-sha256:" + sig[len("ed25519:"):]
        assert verify_provision_signature(SAMPLE_PROVISION_PAYLOAD, bad_sig) is False

    def test_empty_signature_rejects(self):
        assert verify_provision_signature(SAMPLE_PROVISION_PAYLOAD, "") is False

    def test_missing_prefix_rejects(self):
        sig = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        # Just the hex without prefix
        hex_only = sig[len("ed25519:"):]
        assert verify_provision_signature(SAMPLE_PROVISION_PAYLOAD, hex_only) is False

    def test_truncated_signature_rejects(self):
        sig = sign_provision_request(SAMPLE_PROVISION_PAYLOAD)
        truncated = sig[:32]  # Way too short
        assert verify_provision_signature(SAMPLE_PROVISION_PAYLOAD, truncated) is False

    def test_nested_payload_roundtrip(self):
        sig = sign_provision_request(NESTED_PAYLOAD)
        assert verify_provision_signature(NESTED_PAYLOAD, sig) is True

    def test_minimal_payload_roundtrip(self):
        sig = sign_provision_request(MINIMAL_PAYLOAD)
        assert verify_provision_signature(MINIMAL_PAYLOAD, sig) is True


# ── Key ordering invariance ──────────────────────────────────────────────────


class TestCanonicalOrdering:
    """Signature verification is independent of dict key insertion order."""

    def test_different_key_order_same_signature(self):
        payload_a = {"z_field": "last", "a_field": "first", "m_field": "middle"}
        payload_b = {"a_field": "first", "m_field": "middle", "z_field": "last"}
        sig = sign_provision_request(payload_a)
        # Both orderings verify against the same signature because
        # canonical_bytes sorts keys.
        assert verify_provision_signature(payload_a, sig) is True
        assert verify_provision_signature(payload_b, sig) is True

    def test_nested_dict_key_order_invariant(self):
        payload_a = {"outer": {"z": 1, "a": 2}, "id": "test"}
        payload_b = {"id": "test", "outer": {"a": 2, "z": 1}}
        sig = sign_provision_request(payload_a)
        assert verify_provision_signature(payload_b, sig) is True
