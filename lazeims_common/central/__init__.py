"""Central-side halves of the station contract, shared by every Central.

``lazeims-core`` (LAZEIMS) and ``backend-sis`` (ExaMetrics) both issue station
packages and both receive station syncs. Everything in here is the part of those
two jobs that does not depend on which Central is running: package assembly,
signing, ZIP layout, and the sync batch engine.

Each Central supplies only its own two seams — where the data comes from, and
where the syncs land — which is what keeps one station binary able to serve
either of them.

Nothing here imports a database driver or a password hasher: this package is
vendored into the offline station bundle, so its dependencies travel to every
marking centre.
"""

from . import conflict, package, sync
from .conflict import (
    ConflictDecision,
    IncomingWrite,
    Resolution,
    StoredWrite,
    clock_skew_seconds,
    decide,
    normalize_occurred_at,
)
from .package import (
    MachineCredential,
    PackagePreparationError,
    ScopeConflictError,
    assemble_bundle,
    build_manifest,
    build_package_zip,
    compute_configuration_hash,
    compute_package_id,
    new_machine_credential,
)
from .sync import SyncRejected, process_sync_batch

__all__ = [
    "conflict",
    "package",
    "sync",
    "ConflictDecision",
    "IncomingWrite",
    "Resolution",
    "StoredWrite",
    "clock_skew_seconds",
    "decide",
    "normalize_occurred_at",
    "MachineCredential",
    "PackagePreparationError",
    "ScopeConflictError",
    "assemble_bundle",
    "build_manifest",
    "build_package_zip",
    "compute_configuration_hash",
    "compute_package_id",
    "new_machine_credential",
    "SyncRejected",
    "process_sync_batch",
]
