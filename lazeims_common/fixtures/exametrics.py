"""Shared ExaMetrics contract fixtures (§12).

There is no sandbox ExaMetrics tenant (§14.9), so the only way three repos can
prove they agree is to assert the *same JSON* from *both sides*: Central and the
station validate these payloads against a fake transport, and backend-sis
asserts them against its real routes in-process.

They are deliberately **plain dicts, not pydantic models**. The three repos run
three different pydantic versions; the thing that has to agree is bytes on the
wire, and a model would quietly normalise a difference that a real HTTP client
would not. Each fixture does carry a note naming the schema it must validate
against, and ``tests/test_exametrics_fixtures.py`` checks every one of them.

Treat these as immutable. They are module-level dicts for byte-identity across
importers; a test that mutates one corrupts every later assertion in the same
process, so copy before editing (``copy.deepcopy``).
"""

from __future__ import annotations

from typing import Any, Dict

from ..exametrics_digest import collection_digest

# ─── Shared identifiers ──────────────────────────────────────────────────────────

#: ExaMetrics-side exam id. Opaque to the partner and never entered by a human.
EXAM_REF = "exm_01J8Z4RQ7K3N2VYB5D6F7G8H9J"

#: Partner-side exam id — the Central exam UUID, which is why per-tenant
#: uniqueness of ``external_ref`` is free (§14.1).
EXTERNAL_REF = "9c1f4a7e-2b6d-4c58-9f31-8ad0e5b72c14"

#: The processing request these fixtures revolve around.
REQUEST_ID = "prq_01J8Z5A0M4P7QR2STU3VWX4YZ5"

#: Configuration seal and revision the approval is bound to (§5.2).
CONFIGURATION_HASH = "sha256:3f9c1d0b8a7e6f5d4c3b2a190817263544332211ffeeddccbbaa998877665544"
CLOSEOUT_REVISION = 1

CURRENCY = "TZS"
UNIT = "per_student"
#: Minor units per billable student (§14.2a default).
UNIT_AMOUNT = 250


# ─── GET /integration/me ─────────────────────────────────────────────────────────

#: Validates against :class:`lazeims_common.schemas.exametrics.CapabilitiesResponse`.
#:
#: This is the genuine body backend-sis's ``identity_payload()`` emits, including
#: the deprecated ``tenant`` mirror alongside ``tenant_exam``. It is the reason
#: ``CapabilitiesResponse`` is ``extra="ignore"`` (D7): under ``extra="forbid"``
#: the mirror is rejected and this fixture cannot be parsed at all.
IDENTITY_RESPONSE: Dict[str, Any] = {
    "contract_version": "exametrics-integration/v2",
    "tenant_exam": {
        "id": EXAM_REF,
        "name": "FTNA 2026 — Lake Zone",
        "environment": "production",
    },
    "tenant": {
        "id": EXAM_REF,
        "name": "FTNA 2026 — Lake Zone",
        "environment": "production",
    },
    "capabilities": {
        "exam.provision": True,
        "collection.push": True,
        "registrations.extract": True,
        "exam.read": True,
        "processing.request": True,
        "processing.execute": False,
        "results.read": False,
        "results.download": False,
    },
    "limits": {
        "max_payload_mb": 25,
        "max_collection_chunk_size": 5000,
        "rate_limit_per_minute": 120,
    },
    "supported_rules_versions": ["1.0"],
    "approval_status": "PENDING",
    "approval_note": None,
    "requested_scopes": [
        "collection:push",
        "results:process",
        "results:read",
        "results:download",
    ],
    "usable_scopes": ["collection:push"],
    "key_prefix": "lz_ab12cd",
}


# ─── PUT /integration/exams ──────────────────────────────────────────────────────

#: Validates against :class:`~lazeims_common.schemas.exametrics.ExamProvisionRequest`.
EXAM_PROVISION_REQUEST: Dict[str, Any] = {
    "external_ref": EXTERNAL_REF,
    "name": "FTNA 2026",
    "exam_code": "FTNA-2026",
    "level": "FTNA",
    "board": "NECTA",
    "start_date": "2026-10-05",
    "end_date": "2026-10-16",
    "zone_name": "Lake Zone",
    "filling_mode": "TOTAL_MARKS",
    "rules_version": "1.0",
    "configuration_hash": CONFIGURATION_HASH,
    "subjects": [
        {
            "subject_code": "011",
            "subject_name": "HISTORY",
            "subject_short": "011",
            "has_theory_2": False,
            "has_practical": False,
            "theory_max": 100.0,
            "theory_2_max": None,
            "practical_max": None,
            "is_primary": False,
            "is_olevel": True,
            "is_alevel": False,
        },
        {
            "subject_code": "032",
            "subject_name": "PHYSICS",
            "subject_short": "032",
            "has_theory_2": True,
            "has_practical": True,
            "theory_max": 50.0,
            "theory_2_max": 30.0,
            "practical_max": 20.0,
            "is_primary": False,
            "is_olevel": True,
            "is_alevel": False,
        },
    ],
}

#: Validates against :class:`~lazeims_common.schemas.exametrics.ExamProvisionResponse`.
#: The warning is structured (``ProvisionWarning``) so the UI can point at the
#: subject rather than printing prose.
EXAM_PROVISION_RESPONSE: Dict[str, Any] = {
    "exam_ref": EXAM_REF,
    "external_ref": EXTERNAL_REF,
    "state": "UPDATED",
    "created": False,
    "configuration_accepted": True,
    "warnings": [
        {
            "code": "SUBJECT_MAX_MARKS_DIFFERS",
            "message": "Existing definition had theory_max 90; updated to 100.",
            "subject_code": "011",
            "field": "theory_max",
        }
    ],
}


# ─── POST /integration/exams/{ref}/collection ────────────────────────────────────

#: The §1.3 collection payload, deliberately **not** in canonical order and
#: carrying explicit ``null``s, because that is what Central's SQL actually
#: produces. Canonicalising it is what makes
#: ``collection_digest(COLLECTION_PAYLOAD) == frozen_digest()`` hold on both
#: sides of the boundary regardless of row order.
COLLECTION_PAYLOAD: Dict[str, Any] = {
    "schools": [
        {
            "centre_number": "S0201",
            "school_name": "Mwanza Secondary School",
            "school_type": "SECONDARY",
            "region_name": "Mwanza",
            "council_name": "Nyamagana",
            "ward_name": "Mbugani",
        },
        {
            "centre_number": "S0198",
            "school_name": "Ilemela Secondary School",
            "school_type": "SECONDARY",
            "region_name": "Mwanza",
            "council_name": "Ilemela",
            "ward_name": "Kirumba",
        },
    ],
    "subjects": [
        {
            "subject_code": "032",
            "subject_name": "PHYSICS",
            "subject_short": "032",
            "has_theory_2": True,
            "has_practical": True,
            "theory_max": 50.0,
            "theory_2_max": 30.0,
            "practical_max": 20.0,
            "is_primary": False,
            "is_olevel": True,
            "is_alevel": False,
        },
        {
            "subject_code": "011",
            "subject_name": "HISTORY",
            "subject_short": "011",
            "has_theory_2": False,
            "has_practical": False,
            "theory_max": 100.0,
            "theory_2_max": None,
            "practical_max": None,
            "is_primary": False,
            "is_olevel": True,
            "is_alevel": False,
        },
    ],
    "students": [
        {
            "student_id": "S0201-0002",
            "centre_number": "S0201",
            "first_name": "Juma",
            "middle_name": "Hamisi",
            "surname": "Kileo",
            "sex": "M",
        },
        {
            "student_id": "S0198-0001",
            "centre_number": "S0198",
            "first_name": "Neema",
            "middle_name": None,
            "surname": "Shayo",
            "sex": "F",
        },
        {
            "student_id": "S0201-0001",
            "centre_number": "S0201",
            "first_name": "Asha",
            "middle_name": None,
            "surname": "Mwenda",
            "sex": "F",
        },
    ],
    "marks": [
        {
            "student_id": "S0201-0001",
            "centre_number": "S0201",
            "subject_code": "032",
            "theory_marks": 38.0,
            "theory_2_marks": 22.0,
            "practical_marks": 15.0,
            "sat_theory": True,
            "sat_theory_2": True,
            "sat_practical": True,
        },
        {
            "student_id": "S0198-0001",
            "centre_number": "S0198",
            "subject_code": "011",
            "theory_marks": None,
            "theory_2_marks": None,
            "practical_marks": None,
            "sat_theory": False,
        },
        {
            "student_id": "S0201-0002",
            "centre_number": "S0201",
            "subject_code": "011",
            "theory_marks": 55.0,
            "theory_2_marks": None,
            "practical_marks": None,
            "sat_theory": True,
        },
        {
            "student_id": "S0201-0001",
            "centre_number": "S0201",
            "subject_code": "011",
            "theory_marks": 72.0,
            "theory_2_marks": None,
            "practical_marks": None,
            "sat_theory": True,
        },
    ],
}

#: The digest of :data:`COLLECTION_PAYLOAD`, frozen as a literal.
#:
#: Frozen rather than computed so a change to the canonicalisation rules — row
#: ordering or null-dropping — breaks this constant loudly instead of silently
#: agreeing with itself. Both repos assert against this exact string.
FROZEN_COLLECTION_DIGEST = (
    "sha256:c3d9ece85fae3bf732c0d66b0debd46ebcf97a5858774f3433a1b3b765642989"
)


def frozen_digest() -> str:
    """The frozen digest of :data:`COLLECTION_PAYLOAD`.

    A function as well as a constant so a caller can use it as a fixture value
    without importing the name it is compared against.
    """
    return FROZEN_COLLECTION_DIGEST


#: Counts derived from :data:`COLLECTION_PAYLOAD`: 3 candidates across 2 centres
#: with 4 subject registrations. Kept coherent with the payload so backend-sis
#: can push the payload and assert the quote below comes back unchanged.
COLLECTION_COUNTS: Dict[str, int] = {
    "students": 3,
    "centres": 2,
    "subject_registrations": 4,
}


# ─── GET /integration/exams/{ref}/entitlements ───────────────────────────────────

#: Validates against :class:`~lazeims_common.schemas.exametrics.EntitlementsResponse`.
#: Processing paid for and approved, results not readable *yet* because the run
#: has not finished — the §13.4 "not yet" case.
ENTITLEMENTS_APPROVED: Dict[str, Any] = {
    "exam_ref": EXAM_REF,
    "closeout_revision": CLOSEOUT_REVISION,
    "processing": {
        "state": "APPROVED",
        "reason": None,
        "approved_at": "2026-10-31T08:15:00Z",
        "approved_by": "billing@exametrics.example",
        "expires_at": "2026-11-30T08:15:00Z",
        "valid_for_configuration_hash": CONFIGURATION_HASH,
    },
    "results": {
        "state": "LOCKED",
        "reason": "PROCESSING_NOT_COMPLETE",
        "approved_at": None,
        "approved_by": None,
        "expires_at": None,
        "valid_for_configuration_hash": None,
    },
}

#: Validates against :class:`~lazeims_common.schemas.exametrics.EntitlementsResponse`.
#: Nothing requested yet and the key has no ``results:read`` — the §13.4
#: "not allowed" case, which must read differently in the UI from the one above.
ENTITLEMENTS_LOCKED: Dict[str, Any] = {
    "exam_ref": EXAM_REF,
    "closeout_revision": CLOSEOUT_REVISION,
    "processing": {
        "state": "NONE",
        "reason": None,
        "approved_at": None,
        "approved_by": None,
        "expires_at": None,
        "valid_for_configuration_hash": None,
    },
    "results": {
        "state": "LOCKED",
        "reason": "SCOPE_NOT_GRANTED",
        "approved_at": None,
        "approved_by": None,
        "expires_at": None,
        "valid_for_configuration_hash": None,
    },
}


# ─── POST /integration/exams/{ref}/processing-requests ───────────────────────────

#: Validates against :class:`~lazeims_common.schemas.exametrics.ProcessingRequestIn`.
#: ``counts`` are the client's own and exist only for display and comparison —
#: §6.2 forbids pricing from them.
PROCESSING_REQUEST_IN: Dict[str, Any] = {
    "external_ref": EXTERNAL_REF,
    "closeout_revision": CLOSEOUT_REVISION,
    "configuration_hash": CONFIGURATION_HASH,
    "counts": dict(COLLECTION_COUNTS),
    "requested_by": {
        "name": "A. Mwita",
        "username": "amwita",
        "role": "EXAM_ADMIN",
        "user_ref": "b3d1c9f0-5e42-4a77-9c18-2f6ab4e70d31",
        "contact": "a.mwita@zone.example",
    },
    "note": "FTNA 2026 final submission",
}

#: The 202 body — validates against
#: :class:`~lazeims_common.schemas.exametrics.ProcessingQuoteOut`.
#: ``amount`` is ``students × UNIT_AMOUNT`` recomputed server-side.
PROCESSING_REQUEST_PENDING: Dict[str, Any] = {
    "request_id": REQUEST_ID,
    "state": "PENDING_APPROVAL",
    "quote": {
        "currency": CURRENCY,
        "amount": COLLECTION_COUNTS["students"] * UNIT_AMOUNT,
        "unit": UNIT,
        "unit_amount": UNIT_AMOUNT,
        "billable_students": COLLECTION_COUNTS["students"],
        "centres": COLLECTION_COUNTS["centres"],
        "subject_registrations": COLLECTION_COUNTS["subject_registrations"],
        "expires_at": "2026-11-30T06:00:00Z",
    },
    "approval": {
        "method": "EXAMETRICS_CONSOLE",
        "instructions_url": f"https://exametrics.example/admin/exametrics-approvals/{REQUEST_ID}",
        "approver": "ExaMetrics SUPER_ADMIN",
    },
    "next_poll_after": "2026-10-31T06:00:00Z",
    "replayed": False,
}

#: The stored request once approved — validates against
#: :class:`~lazeims_common.schemas.exametrics.ProcessingRequestOut`.
#: ``billable_count`` is the count the amount is frozen against: at ``process``
#: time a smaller count still runs, a larger one is a 409
#: ``QUOTE_COUNTS_EXCEEDED`` (§14.4b).
PROCESSING_REQUEST_APPROVED: Dict[str, Any] = {
    "request_id": REQUEST_ID,
    "exam_ref": EXAM_REF,
    "external_ref": EXTERNAL_REF,
    "closeout_revision": CLOSEOUT_REVISION,
    "configuration_hash": CONFIGURATION_HASH,
    "state": "APPROVED",
    "quote": {
        "currency": CURRENCY,
        "amount": COLLECTION_COUNTS["students"] * UNIT_AMOUNT,
        "unit": UNIT,
        "unit_amount": UNIT_AMOUNT,
        "billable_students": COLLECTION_COUNTS["students"],
        "centres": COLLECTION_COUNTS["centres"],
        "subject_registrations": COLLECTION_COUNTS["subject_registrations"],
        "expires_at": "2026-11-30T06:00:00Z",
    },
    "counts": dict(COLLECTION_COUNTS),
    "billable_count": COLLECTION_COUNTS["students"],
    "requested_by": {
        "name": "A. Mwita",
        "username": "amwita",
        "role": "EXAM_ADMIN",
        "user_ref": "b3d1c9f0-5e42-4a77-9c18-2f6ab4e70d31",
        "contact": "a.mwita@zone.example",
    },
    "note": "FTNA 2026 final submission",
    "run_id": "run_01J8Z6B1N5Q8RS3TUV4WXY5Z6A",
    "requested_at": "2026-10-31T05:58:00Z",
    "decided_at": "2026-10-31T08:15:00Z",
    "decided_by": "billing@exametrics.example",
    "decision_reason": "Invoice INV-2026-0417 settled.",
    "expires_at": "2026-11-30T08:15:00Z",
    "next_poll_after": "2026-10-31T08:20:00Z",
}


# ─── Webhook (§7.3) ──────────────────────────────────────────────────────────────

#: Validates against :class:`~lazeims_common.schemas.exametrics.WebhookEnvelope`.
#: The signature is over the canonical JSON of this body with ``signature``
#: removed; this literal is not a real HMAC and exists to pin the shape, so a
#: signature-verification test must recompute it with its own secret.
WEBHOOK_COMPLETED: Dict[str, Any] = {
    "event": "processing.completed",
    "exam_ref": EXAM_REF,
    "external_ref": EXTERNAL_REF,
    "request_id": REQUEST_ID,
    "state": "COMPLETED",
    "occurred_at": "2026-10-31T09:02:11Z",
    "signature": "hmac-sha256:0000000000000000000000000000000000000000000000000000000000000000",
}


# ─── Error envelope (§8) ─────────────────────────────────────────────────────────

#: Validates against :class:`~lazeims_common.schemas.exametrics.ErrorEnvelope`,
#: with every entry of ``details`` validating against
#: :class:`~lazeims_common.schemas.exametrics.RowValidationDetail`.
#: Row-addressable, so the operator UI can point at the candidate (§13.3) rather
#: than showing a wall of text.
VALIDATION_FAILED_422: Dict[str, Any] = {
    "error": {
        "code": "VALIDATION_FAILED",
        "message": "2 marks rows were rejected.",
        "details": [
            {
                "student_id": "S0201-0001",
                "code": "MARK_ABOVE_MAXIMUM",
                "message": "Theory mark 38.0 exceeds the maximum 30.0 for paper THEORY2.",
                "subject_code": "032",
                "paper": "THEORY2",
            },
            {
                "student_id": "S0198-0001",
                "code": "MARK_WITHOUT_ATTENDANCE",
                "message": "A mark was supplied for a candidate recorded absent.",
                "subject_code": "011",
                "paper": "THEORY1",
            },
        ],
        "request_id": "req_01J8Z7C2P6R9ST4UVW5XYZ6A7B",
    }
}


def digest_of_collection_payload() -> str:
    """Recompute the digest of :data:`COLLECTION_PAYLOAD`.

    Only useful for the assertion that the computed value still equals
    :func:`frozen_digest`; production code should call
    :func:`lazeims_common.exametrics_digest.collection_digest` directly.
    """
    return collection_digest(COLLECTION_PAYLOAD)


__all__ = [
    "EXAM_REF",
    "EXTERNAL_REF",
    "REQUEST_ID",
    "CONFIGURATION_HASH",
    "CLOSEOUT_REVISION",
    "CURRENCY",
    "UNIT",
    "UNIT_AMOUNT",
    "IDENTITY_RESPONSE",
    "EXAM_PROVISION_REQUEST",
    "EXAM_PROVISION_RESPONSE",
    "COLLECTION_PAYLOAD",
    "COLLECTION_COUNTS",
    "FROZEN_COLLECTION_DIGEST",
    "frozen_digest",
    "digest_of_collection_payload",
    "ENTITLEMENTS_APPROVED",
    "ENTITLEMENTS_LOCKED",
    "PROCESSING_REQUEST_IN",
    "PROCESSING_REQUEST_PENDING",
    "PROCESSING_REQUEST_APPROVED",
    "WEBHOOK_COMPLETED",
    "VALIDATION_FAILED_422",
]
