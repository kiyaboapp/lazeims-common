"""Portable exchange envelope — signed, encrypted, recipient-bound, expiring,
replay-protected. Used when a station can never reach Central directly.

Both the events and the acknowledgements travel in the same envelope format, and
the portable import path on Central reuses the exact same sync application
service as direct HTTPS — a different transport, never different logic.

Encryption + authentication: Fernet (AES-128-CBC + HMAC-SHA256, with a bound
timestamp for TTL). The Fernet key is provisioned SEPARATELY from the medium
(never shipped beside the payload). Recipient binding, nonce (replay), direction
and sequence live inside the authenticated plaintext.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken

from .enums import RejectionCode
from .errors import ValidationError

# Envelope directions
DIRECTION_EVENTS = "EVENTS"
DIRECTION_ACKS = "ACKNOWLEDGEMENTS"
DIRECTION_RECONCILIATION = "RECONCILIATION"


def generate_key() -> str:
    """Generate a new Fernet key (base64 str). Provision this out-of-band."""
    return Fernet.generate_key().decode("ascii")


@dataclass
class OpenedEnvelope:
    exchange_id: str
    sender: str
    recipient: str
    direction: str
    sequence: int
    nonce: str
    payload: dict


def seal(
    payload: dict,
    *,
    key: str,
    sender: str,
    recipient: str,
    direction: str,
    sequence: int,
    exchange_id: str | None = None,
) -> str:
    """Seal ``payload`` into an encrypted, authenticated portable token."""
    inner = {
        "exchange_id": exchange_id or ("xch_" + uuid.uuid4().hex),
        "sender": sender,
        "recipient": recipient,
        "direction": direction,
        "sequence": sequence,
        "nonce": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    token = Fernet(key.encode("ascii")).encrypt(json.dumps(inner).encode("utf-8"))
    return token.decode("ascii")


def open_envelope(
    token: str,
    *,
    key: str,
    expected_recipient: str,
    ttl_seconds: int = 7 * 24 * 3600,
    seen_nonces: set[str] | None = None,
) -> OpenedEnvelope:
    """Decrypt + authenticate a token and enforce recipient/expiry/replay.

    Raises :class:`ValidationError` with a stable code on any failure.
    """
    try:
        raw = Fernet(key.encode("ascii")).decrypt(token.encode("ascii"), ttl=ttl_seconds)
    except InvalidToken as exc:
        raise ValidationError(
            RejectionCode.CONFIGURATION_MISMATCH,
            "Portable envelope is invalid, tampered, or expired.",
        ) from exc

    inner = json.loads(raw.decode("utf-8"))
    if inner.get("recipient") != expected_recipient:
        raise ValidationError(
            RejectionCode.OUTSIDE_STATION_SCOPE,
            "Portable envelope is addressed to a different recipient.",
            {"expected": expected_recipient, "actual": inner.get("recipient")},
        )

    nonce = inner.get("nonce")
    if seen_nonces is not None:
        if nonce in seen_nonces:
            raise ValidationError(
                RejectionCode.EVENT_ID_PAYLOAD_CONFLICT,
                "Portable envelope replay detected (nonce already seen).",
                {"nonce": nonce},
            )
        seen_nonces.add(nonce)

    return OpenedEnvelope(
        exchange_id=inner["exchange_id"],
        sender=inner["sender"],
        recipient=inner["recipient"],
        direction=inner["direction"],
        sequence=inner["sequence"],
        nonce=nonce,
        payload=inner["payload"],
    )
