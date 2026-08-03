"""Tests for Ed25519 signing and package contract (station-package/v1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lazeims_common.hashing import canonical_bytes
from lazeims_common.schemas.station_package import (
    CONTRACT_VERSION,
    DataEntererScopeEntry,
    MachineCredentialMeta,
    MachineCredentialPayload,
    PackageErrorCode,
    PackageScope,
    SigningMeta,
    StationAdminEntry,
    StationPackageManifest,
)
from lazeims_common.signing import (
    generate_test_keypair,
    get_public_key_pem,
    get_signing_private_key,
    get_signing_public_key,
    load_public_key_from_pem,
    sign_data,
    sign_package_manifest,
    verify_package_signature,
    verify_signature,
)


class TestEd25519Signing:
    """Ed25519 key generation, signing, and verification."""

    def test_test_keypair_is_deterministic(self):
        k1, pub1 = generate_test_keypair()
        k2, pub2 = generate_test_keypair()
        # Same seed -> same key bytes
        from cryptography.hazmat.primitives import serialization
        b1 = k1.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
        b2 = k2.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
        assert b1 == b2

    def test_sign_and_verify_roundtrip(self):
        data = {"station_code": "TEST-01", "version": 1, "items": [1, 2, 3]}
        sig = sign_data(data)
        assert verify_signature(data, sig)

    def test_tampered_data_fails_verification(self):
        data = {"station_code": "TEST-01", "version": 1}
        sig = sign_data(data)
        data["version"] = 2
        assert not verify_signature(data, sig)

    def test_wrong_signature_fails(self):
        data = {"hello": "world"}
        assert not verify_signature(data, "0" * 128)

    def test_invalid_hex_fails_gracefully(self):
        data = {"hello": "world"}
        assert not verify_signature(data, "not-hex")

    def test_sign_package_manifest_prefix(self):
        manifest = {"package_id": "pkg_abc", "version": 1}
        sig = sign_package_manifest(manifest)
        assert sig.startswith("ed25519:")
        assert verify_package_signature(manifest, sig)

    def test_verify_package_signature_wrong_prefix(self):
        manifest = {"package_id": "pkg_abc", "version": 1}
        assert not verify_package_signature(manifest, "hmac-sha256:abc123")

    def test_public_key_pem_roundtrip(self):
        pem = get_public_key_pem()
        assert "BEGIN PUBLIC KEY" in pem
        loaded = load_public_key_from_pem(pem)
        # Verify with loaded key
        data = {"test": True}
        sig = sign_data(data)
        assert verify_signature(data, sig, public_key=loaded)

    def test_verify_with_explicit_public_key(self):
        _, pub = generate_test_keypair()
        data = {"explicit": "key-test"}
        sig = sign_data(data)
        assert verify_signature(data, sig, public_key=pub)

    def test_different_key_rejects(self):
        """A signature from one key is NOT valid with a different public key."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        other_key = Ed25519PrivateKey.generate()
        other_pub = other_key.public_key()
        data = {"only_for_test_key": True}
        sig = sign_data(data)
        # Verify with wrong key should fail
        assert not verify_signature(data, sig, public_key=other_pub)


class TestPackageContract:
    """Station package manifest schema validation (station-package/v1)."""

    def test_contract_version(self):
        assert CONTRACT_VERSION == "station-package/v1"

    def test_minimal_manifest_roundtrip(self):
        m = StationPackageManifest(
            package_id="pkg_test123",
            package_version=1,
            rules_version="1.0",
            software_min_version="1.0.0",
            station_code="MWANZA-2",
            exam_id="uuid-here",
            configuration_hash="sha256:abc",
            issued_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            scope=PackageScope(schools=["S001"], subjects=["011"], papers=["THEORY1"]),
            machine_credential=MachineCredentialMeta(credential_id="mc_abc123"),
        )
        data = m.model_dump(mode="json")
        assert data["contract_version"] == "station-package/v1"
        assert data["machine_credential"]["credential_id"] == "mc_abc123"
        assert data["signing"]["algorithm"] == "ed25519"

    def test_supersession_field(self):
        m = StationPackageManifest(
            package_id="pkg_super",
            package_version=2,
            supersedes_package_id="pkg_v1",
            rules_version="1.0",
            software_min_version="1.0.0",
            station_code="ST-01",
            exam_id="uuid",
            configuration_hash="sha256:x",
            issued_at=datetime.now(timezone.utc),
            scope=PackageScope(schools=["S1"], subjects=["011"], papers=["THEORY1"]),
            machine_credential=MachineCredentialMeta(credential_id="mc_xyz"),
        )
        assert m.supersedes_package_id == "pkg_v1"

    def test_central_url_included(self):
        m = StationPackageManifest(
            package_id="pkg_url",
            package_version=1,
            rules_version="1.0",
            software_min_version="1.0.0",
            station_code="ST-01",
            exam_id="uuid",
            configuration_hash="sha256:x",
            issued_at=datetime.now(timezone.utc),
            scope=PackageScope(schools=["S1"], subjects=["011"], papers=["THEORY1"]),
            central_base_url="https://central.lazeims.example",
            machine_credential=MachineCredentialMeta(credential_id="mc_x"),
        )
        assert m.central_base_url == "https://central.lazeims.example"

    def test_de_scope_data(self):
        de = DataEntererScopeEntry(
            assignment_id=42,
            initials="JK",
            pin_hash="$argon2id$...",
            school_centre_numbers=["S001", "S002"],
            subject_codes=["011"],
        )
        assert de.school_centre_numbers == ["S001", "S002"]

    def test_admin_entry(self):
        admin = StationAdminEntry(
            assignment_id=1,
            username="chief-it-user",
            password_hash="$argon2id$...",
        )
        assert admin.username == "chief-it-user"

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            StationPackageManifest(
                package_id="pkg_x",
                package_version=1,
                rules_version="1.0",
                software_min_version="1.0.0",
                station_code="ST-01",
                exam_id="uuid",
                configuration_hash="sha256:x",
                issued_at=datetime.now(timezone.utc),
                scope=PackageScope(schools=["S1"], subjects=["011"], papers=["THEORY1"]),
                machine_credential=MachineCredentialMeta(credential_id="mc_x"),
                unexpected_field="not allowed",
            )


class TestMachineCredentialPayload:
    """Machine credential sensitive payload schema."""

    def test_payload_structure(self):
        p = MachineCredentialPayload(
            credential_id="mc_abc",
            package_id="pkg_test",
            station_code="MWANZA-2",
            secret="super-secret-token",
            central_base_url="https://central.example",
        )
        data = p.model_dump(mode="json")
        assert data["secret"] == "super-secret-token"
        assert data["central_base_url"] == "https://central.example"


class TestPackageErrorCodes:
    """Error codes are stable strings."""

    def test_error_codes_are_strings(self):
        assert PackageErrorCode.SCOPE_CONFLICT == "SCOPE_CONFLICT"
        assert PackageErrorCode.CENTRAL_URL_NOT_CONFIGURED == "CENTRAL_URL_NOT_CONFIGURED"
        assert PackageErrorCode.MISSING_APPLICABLE_PAPERS == "MISSING_APPLICABLE_PAPERS"


class TestSignedManifestIntegration:
    """End-to-end: build manifest, sign, verify."""

    def test_full_manifest_sign_verify(self):
        m = StationPackageManifest(
            package_id="pkg_integration_test",
            package_version=1,
            supersedes_package_id=None,
            rules_version="1.0",
            software_min_version="1.0.0",
            station_code="TEST-STATION-01",
            exam_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            exam_code="LAKE-ZONE-F4",
            exam_name="Lake Zone Form IV",
            configuration_hash="sha256:abcdef1234567890",
            issued_at=datetime(2026, 8, 1, 3, 0, 0, tzinfo=timezone.utc),
            scope=PackageScope(
                schools=["S001", "S002"],
                subjects=["011", "012"],
                papers=["THEORY1", "THEORY2"],
            ),
            central_base_url="https://central.lazeims.tz",
            machine_credential=MachineCredentialMeta(
                credential_id="mc_abcdef123456",
                algorithm="argon2id",
            ),
            signing=SigningMeta(algorithm="ed25519"),
            station_admin=StationAdminEntry(
                assignment_id=1,
                username="chief-it",
                password_hash="$argon2id$v=19$...",
            ),
            data_enterers=[
                DataEntererScopeEntry(
                    assignment_id=10,
                    initials="JK",
                    pin_hash="$argon2id$v=19$...",
                    school_centre_numbers=["S001"],
                    subject_codes=["011"],
                ),
            ],
        )
        manifest_data = m.model_dump(mode="json")
        sig = sign_package_manifest(manifest_data)

        # Verify with default (test) key
        assert verify_package_signature(manifest_data, sig)

        # Tamper check
        manifest_data["station_code"] = "TAMPERED"
        assert not verify_package_signature(manifest_data, sig)
