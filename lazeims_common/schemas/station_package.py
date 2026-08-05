"""Canonical station package manifest contract (``station-package/v1``).

Features:
- Package supersession (supersedes_package_id)
- Central URL for online-first Station setup
- Ed25519 signing metadata
- Package-bound machine credential metadata
- Data Enterer scope data and admin username
- Applicable papers per subject
- File hashes for integrity verification
- Stable error codes for package preparation failures
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "station-package/v1"


class PackageScope(BaseModel):
    """Scope with explicit applicable papers per school/subject combination."""

    model_config = ConfigDict(extra="forbid")

    schools: list[str] = Field(default_factory=list, description="Centre numbers")
    subjects: list[str] = Field(default_factory=list, description="Subject codes")
    papers: list[str] = Field(default_factory=list, description="Applicable paper types")


class DataEntererScopeEntry(BaseModel):
    """A single DE's scope assignment, included in the package for local auth."""

    model_config = ConfigDict(extra="forbid")

    assignment_id: int
    initials: str
    pin_hash: str
    school_centre_numbers: list[str] = Field(default_factory=list)
    subject_codes: list[str] = Field(default_factory=list)


class StationAdminEntry(BaseModel):
    """Station admin credential metadata (not the plaintext)."""

    model_config = ConfigDict(extra="forbid")

    assignment_id: int
    username: str
    password_hash: str


class MachineCredentialMeta(BaseModel):
    """Package-bound machine credential — the identifier is carried in the
    manifest; the plaintext secret is in a separate sensitive file."""

    model_config = ConfigDict(extra="forbid")

    credential_id: str = Field(description="Stable identifier for this machine credential")
    algorithm: str = Field(default="argon2id", description="Hash algorithm used for storage")


class SigningMeta(BaseModel):
    """Ed25519 signing metadata."""

    model_config = ConfigDict(extra="forbid")

    algorithm: str = Field(default="ed25519")
    public_key_id: str = Field(
        default="",
        description="Key identifier to allow future key rotation"
    )


class StationPackageManifest(BaseModel):
    """Produced by Central, consumed by the Station on package import.

    Every ID here is a natural key (centre number, subject code, paper type) —
    never a database integer id.
    """

    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default=CONTRACT_VERSION)
    package_id: str
    package_version: int
    supersedes_package_id: str | None = Field(
        default=None,
        description="Package ID that this version supersedes (for import ordering)"
    )
    rules_version: str
    schema_min_version: str = Field(default="1.0")
    software_min_version: str
    station_code: str
    exam_id: str
    exam_code: str = Field(default="", description="Human-readable exam code")
    exam_name: str = Field(default="", description="Human-readable exam name")
    configuration_hash: str
    issued_at: datetime
    expires_at: datetime | None = None
    scope: PackageScope
    central_base_url: str = Field(
        default="",
        description="Central's public URL for online-first sync/setup"
    )
    machine_credential: MachineCredentialMeta
    signing: SigningMeta = Field(default_factory=SigningMeta)
    station_admin: StationAdminEntry | None = None
    data_enterers: list[DataEntererScopeEntry] = Field(default_factory=list)


class PackageFileHashes(BaseModel):
    """SHA-256 hashes of every file in the package ZIP (for verification)."""

    model_config = ConfigDict(extra="forbid")

    manifest_json: str
    seed_json: str
    credentials_json: str
    machine_credential_json: str


class MachineCredentialPayload(BaseModel):
    """The sensitive machine-credential.json content (plaintext secret).

    This is included only in the package ZIP, never stored centrally.
    """

    model_config = ConfigDict(extra="forbid")

    credential_id: str
    package_id: str
    station_code: str
    secret: str = Field(description="Random plaintext machine secret (protect after import)")
    central_base_url: str = Field(default="")


# ── Error codes for package preparation ──────────────────────────────────────

class PackageErrorCode:
    """Stable error codes for package preparation failures."""

    SCOPE_CONFLICT = "SCOPE_CONFLICT"
    SCOPE_CONFLICT_DETAIL = "SCOPE_CONFLICT_DETAIL"
    SCOPE_VIOLATION = "SCOPE_VIOLATION"
    MISSING_APPLICABLE_PAPERS = "MISSING_APPLICABLE_PAPERS"
    CENTRAL_URL_NOT_CONFIGURED = "CENTRAL_URL_NOT_CONFIGURED"
    SIGNING_KEY_UNAVAILABLE = "SIGNING_KEY_UNAVAILABLE"
    CREDENTIAL_GENERATION_FAILED = "CREDENTIAL_GENERATION_FAILED"
    NO_REGISTERED_STUDENTS = "NO_REGISTERED_STUDENTS"
