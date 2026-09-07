"""Central-side package assembly for ``station-package/v1``.

Why this is here and not in either Central
------------------------------------------
Two Centrals issue station packages — ``lazeims-core`` for LAZEIMS and
``backend-sis`` for ExaMetrics — and one station binary imports both. Everything
in this module is the part of that job that is *identical* for both: how a
package id is derived, how a machine credential is minted, how the manifest is
assembled and signed, and what bytes go into the ZIP.

It was previously written twice, once per Central, which is how the two drifted:
one signed with Ed25519 through :mod:`lazeims_common.signing`, the other with
HMAC-SHA256 over a hand-built dict, producing an artifact a station could not
import at all. A second, quieter divergence survived even after that was fixed —
each Central had its own private ``_canonical`` JSON writer, so "the canonical
form" had two definitions in a codebase that already defines it once in
:mod:`lazeims_common.hashing`.

What stays with each Central
----------------------------
Only the two seams that genuinely differ:

* **where the data comes from** — the ``seed`` dict, built from that Central's own
  tables (ExaMetrics has ``students``/``student_subjects``; LAZEIMS has
  ``exam_students``/``exam_student_subjects``);
* **where it syncs to and who signs** — ``central_base_url`` and the Ed25519 key,
  both per-deployment configuration.

Deliberately dependency-free
----------------------------
No SQLAlchemy, no argon2. ``lazeims_common`` is vendored into the offline station
bundle, so adding a database or hashing dependency here would ship it to every
marking centre. Secret hashing is injected instead: both Centrals pass their own
Argon2id hasher, which is also what makes every function here testable without a
database.
"""

from __future__ import annotations

import hashlib
import io
import secrets
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from ..hashing import canonical_bytes, sha256_hex, sha256_prefixed
from ..schemas.station_package import (
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
from ..signing import sign_package_manifest

__all__ = [
    "SOFTWARE_MIN_VERSION",
    "MachineCredential",
    "PackagePreparationError",
    "ScopeConflictError",
    "compute_package_id",
    "compute_configuration_hash",
    "new_machine_credential",
    "build_manifest",
    "assemble_bundle",
    "build_package_zip",
    "PACKAGE_FILES",
]

# The minimum station build that can import a package produced here. Bumped only
# when a package starts relying on station behaviour older builds lack; the
# station then refuses the import with UPGRADE_REQUIRED instead of misreading it.
SOFTWARE_MIN_VERSION = "1.0.0"

# The file names the station reads by name. Changing any of these is a contract
# break: station/package_import.py raises PACKAGE_MALFORMED on a missing entry.
PACKAGE_FILES = ("manifest.json", "seed.json", "machine-credential.json", "signature")


class PackagePreparationError(Exception):
    """A package could not be prepared, carrying a stable contract error code.

    Codes come from :class:`~lazeims_common.schemas.station_package.PackageErrorCode`
    so an operator sees which of several very different failures occurred rather
    than one anonymous message.
    """

    def __init__(self, code: str, message: str, detail: dict | None = None):
        self.code = code
        self.message = message
        self.detail = detail or {}
        super().__init__(message)


class ScopeConflictError(Exception):
    """Raised when a scope is already assigned to a different station."""

    def __init__(self, conflicts: list[dict]):
        self.conflicts = conflicts
        super().__init__(f"{len(conflicts)} scope conflict(s) detected")


@dataclass(frozen=True, slots=True)
class MachineCredential:
    """A freshly minted machine credential.

    ``secret`` is plaintext and exists only long enough to be written into the
    package ZIP. Only ``secret_hash`` may be persisted.
    """

    credential_id: str
    secret: str
    secret_hash: str


def compute_configuration_hash(seed: dict) -> str:
    """The seed's integrity hash, ``sha256:``-prefixed.

    The station recomputes this from ``seed.json`` and refuses the import on any
    difference, so it must come from the shared canonical hasher. A local
    ``json.dumps`` would differ on separators alone and fail every import with
    ``CONFIGURATION_MISMATCH``.
    """
    return sha256_prefixed(seed)


def compute_package_id(
    *, station_code: str, package_version: int, configuration_hash: str
) -> str:
    """Derive the package id.

    Content-addressed rather than random: regenerating an identical package for
    the same station and version yields the same id, so a re-issued bundle is
    recognisably the same bundle.
    """
    digest = sha256_hex(f"{station_code}:{package_version}:{configuration_hash}")
    return f"pkg_{digest[:24]}"


def new_machine_credential(hash_secret: Callable[[str], str]) -> MachineCredential:
    """Mint a package-bound machine credential.

    ``hash_secret`` must produce an Argon2id hash — the manifest declares
    ``algorithm: "argon2id"`` and the station has no way to negotiate another.
    It is injected so this module needs no hashing dependency of its own.
    """
    credential_id = f"mc_{secrets.token_hex(12)}"
    secret = secrets.token_urlsafe(32)
    return MachineCredential(
        credential_id=credential_id, secret=secret, secret_hash=hash_secret(secret)
    )


def build_manifest(
    *,
    package_id: str,
    package_version: int,
    supersedes_package_id: str | None,
    rules_version: str,
    station_code: str,
    exam_id: str,
    exam_code: str = "",
    exam_name: str = "",
    configuration_hash: str,
    schools: list[str],
    subjects: list[str],
    papers: list[str],
    central_base_url: str,
    machine_credential_id: str,
    station_admin: StationAdminEntry | None = None,
    data_enterers: list[DataEntererScopeEntry] | None = None,
    software_min_version: str = SOFTWARE_MIN_VERSION,
    public_key_id: str = "",
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> StationPackageManifest:
    """Assemble the manifest.

    Returns the model rather than a dict so a missing or misspelled field fails
    here, at the Central that can still fix it, instead of at a station on a
    marking centre floor with no internet.
    """
    return StationPackageManifest(
        contract_version=CONTRACT_VERSION,
        package_id=package_id,
        package_version=package_version,
        supersedes_package_id=supersedes_package_id,
        rules_version=rules_version,
        software_min_version=software_min_version,
        station_code=station_code,
        exam_id=exam_id,
        exam_code=exam_code,
        exam_name=exam_name,
        configuration_hash=configuration_hash,
        issued_at=issued_at or datetime.now(timezone.utc),
        expires_at=expires_at,
        scope=PackageScope(schools=schools, subjects=subjects, papers=papers),
        central_base_url=central_base_url,
        machine_credential=MachineCredentialMeta(
            credential_id=machine_credential_id, algorithm="argon2id"
        ),
        signing=SigningMeta(algorithm="ed25519", public_key_id=public_key_id),
        station_admin=station_admin,
        data_enterers=data_enterers or [],
    )


def assemble_bundle(
    *,
    manifest: StationPackageManifest,
    seed: dict,
    machine_credential: MachineCredential,
    station_code: str,
    central_base_url: str,
) -> dict:
    """Serialise, sign, and return the package bundle.

    The signature covers the *serialised* manifest, which is the dict that lands
    in ``manifest.json`` and the one the station will re-hash. Signing the model
    or any other representation would verify here and fail there.
    """
    manifest_json = manifest.model_dump(mode="json")
    credential_payload = MachineCredentialPayload(
        credential_id=machine_credential.credential_id,
        package_id=manifest.package_id,
        station_code=station_code,
        secret=machine_credential.secret,
        central_base_url=central_base_url,
    ).model_dump(mode="json")

    return {
        "contract_version": CONTRACT_VERSION,
        "manifest": manifest_json,
        "seed": seed,
        "signature": sign_package_manifest(manifest_json),
        "machine_credential": credential_payload,
    }


def build_package_zip(bundle: dict, *, central_name: str = "LAZEIMS") -> bytes:
    """Write the package ZIP.

    JSON is written in canonical form — the same form that was signed and hashed —
    so the bytes on disk are the bytes the signature covers. Both sides re-parse
    before verifying, so a pretty-printed file would still validate; writing the
    canonical form means ``SHA256SUMS`` describes the signed payload rather than a
    cosmetic variant of it.

    ``central_name`` only labels the README. The operating instructions are
    identical for both Centrals because it is the same station software.
    """
    manifest = bundle.get("manifest") or {}
    seed = bundle.get("seed") or {}
    signature = bundle.get("signature") or ""
    machine_credential = bundle.get("machine_credential") or {}

    files: dict[str, bytes] = {
        "manifest.json": canonical_bytes(manifest),
        "seed.json": canonical_bytes(seed),
        "machine-credential.json": canonical_bytes(machine_credential),
        "signature": signature.encode("ascii"),
    }

    sha256sums = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {name}\n" for name, content in files.items()
    )

    readme = (
        f"{central_name} exam package\n"
        f"{'=' * (len(central_name) + 14)}\n\n"
        f"Station     : {manifest.get('station_code', '?')}\n"
        f"Exam        : {manifest.get('exam_name') or manifest.get('exam_code') or manifest.get('exam_id')}\n"
        f"Version     : {manifest.get('package_version')}\n"
        f"Contract    : {manifest.get('contract_version')}\n"
        f"Issued at   : {manifest.get('issued_at')}\n"
        f"Syncs to    : {manifest.get('central_base_url')}\n\n"
        "Import this file from the station's local admin console\n"
        "(http://<station-ip>:8080). One station installation serves every exam\n"
        "and every package — do NOT extract this ZIP by hand.\n\n"
        "The station verifies the signature and the seed integrity before writing\n"
        "anything, so a bundle meant for another station or another exam is\n"
        "refused rather than partially applied.\n\n"
        "machine-credential.json carries this station's sync secret in plaintext\n"
        "and is issued exactly once. Keep this ZIP off shared drives and email.\n"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
        zf.writestr("SHA256SUMS", sha256sums)
        zf.writestr("README.txt", readme)
    return buf.getvalue()
