from __future__ import annotations

import pytest

from lazeims_common.errors import ValidationError
from lazeims_common.portable import (
    DIRECTION_EVENTS,
    generate_key,
    open_envelope,
    seal,
)
from lazeims_common.reconcile import (
    counts_from_records,
    normalize_item_record,
    normalize_total_record,
    reconcile,
    scope_digest,
)


# ---- reconcile ----

def test_scope_digest_order_independent():
    a = [normalize_total_record("S-2", True, 50), normalize_total_record("S-1", True, 60)]
    b = [normalize_total_record("S-1", True, 60), normalize_total_record("S-2", True, 50)]
    assert scope_digest(a) == scope_digest(b)


def test_scope_digest_changes_with_data():
    a = [normalize_total_record("S-1", True, 60)]
    b = [normalize_total_record("S-1", True, 61)]
    assert scope_digest(a) != scope_digest(b)


def test_item_records_normalized_equal():
    a = normalize_item_record("S-1", True, {"1": 8, "2": 6})
    b = normalize_item_record("S-1", True, {"2": 6, "1": 8})
    assert scope_digest([a]) == scope_digest([b])


def test_reconcile_matched_mismatched():
    d1 = scope_digest([normalize_total_record("S-1", True, 60)])
    d2 = scope_digest([normalize_total_record("S-1", True, 60)])
    d3 = scope_digest([normalize_total_record("S-1", True, 61)])
    assert reconcile(d1, d2) == "MATCHED"
    assert reconcile(d1, d3) == "MISMATCHED"


def test_counts():
    recs = [
        normalize_total_record("S-1", True, 60),
        normalize_total_record("S-2", False, None),
        normalize_total_record("S-3", True, 0),
    ]
    c = counts_from_records(recs)
    assert c.present == 2 and c.absent == 1 and c.with_marks == 2  # S-2 absent no total


# ---- portable envelope ----

def test_portable_round_trip():
    key = generate_key()
    token = seal({"hello": "world"}, key=key, sender="ST-1", recipient="CENTRAL",
                 direction=DIRECTION_EVENTS, sequence=1)
    opened = open_envelope(token, key=key, expected_recipient="CENTRAL")
    assert opened.payload == {"hello": "world"}
    assert opened.direction == DIRECTION_EVENTS and opened.sender == "ST-1"


def test_portable_wrong_recipient_rejected():
    key = generate_key()
    token = seal({"x": 1}, key=key, sender="ST-1", recipient="CENTRAL",
                 direction=DIRECTION_EVENTS, sequence=1)
    with pytest.raises(ValidationError) as exc:
        open_envelope(token, key=key, expected_recipient="OTHER")
    assert exc.value.code.value == "OUTSIDE_STATION_SCOPE"


def test_portable_tamper_rejected():
    key = generate_key()
    token = seal({"x": 1}, key=key, sender="ST-1", recipient="CENTRAL",
                 direction=DIRECTION_EVENTS, sequence=1)
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    with pytest.raises(ValidationError):
        open_envelope(tampered, key=key, expected_recipient="CENTRAL")


def test_portable_wrong_key_rejected():
    token = seal({"x": 1}, key=generate_key(), sender="ST-1", recipient="CENTRAL",
                 direction=DIRECTION_EVENTS, sequence=1)
    with pytest.raises(ValidationError):
        open_envelope(token, key=generate_key(), expected_recipient="CENTRAL")


def test_portable_replay_rejected():
    key = generate_key()
    token = seal({"x": 1}, key=key, sender="ST-1", recipient="CENTRAL",
                 direction=DIRECTION_EVENTS, sequence=1)
    seen: set[str] = set()
    open_envelope(token, key=key, expected_recipient="CENTRAL", seen_nonces=seen)
    with pytest.raises(ValidationError) as exc:
        open_envelope(token, key=key, expected_recipient="CENTRAL", seen_nonces=seen)
    assert exc.value.code.value == "EVENT_ID_PAYLOAD_CONFLICT"
