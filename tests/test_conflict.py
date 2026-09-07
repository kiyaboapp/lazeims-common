"""Write-conflict resolution: one case per rule.

The unit under test is pure, so every rule is stated as inputs and a verdict
rather than as a scenario that needs a database to reproduce.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from lazeims_common.central.conflict import (
    IncomingWrite,
    Resolution,
    StoredWrite,
    clock_skew_seconds,
    decide,
    normalize_occurred_at,
)

T0 = datetime(2026, 8, 27, 9, 0, tzinfo=timezone.utc)
LATER = T0 + timedelta(hours=1)


def _in(*, station="MWANZA-1", version=1, at=T0, value="sha256:aaa"):
    return IncomingWrite(station_code=station, local_version=version,
                         occurred_at=at, value_hash=value)


def _stored(*, station="MWANZA-1", version=1, at=T0, value="sha256:aaa"):
    return StoredWrite(station_code=station, local_version=version,
                       occurred_at=at, value_hash=value)


# ── Clock measurement ────────────────────────────────────────────────────────

def test_skew_is_measured_not_assumed():
    server = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
    station = datetime(2026, 8, 27, 11, 55, tzinfo=timezone.utc)  # 5 min behind
    assert clock_skew_seconds(station, server) == 300.0
    # A station whose clock runs fast yields a negative correction.
    assert clock_skew_seconds(server + timedelta(minutes=2), server) == -120.0
    # An older station build sends nothing: no correction rather than no decision.
    assert clock_skew_seconds(None, server) == 0.0


def test_normalisation_restates_a_wrong_clock_on_centrals():
    """A dead CMOS battery is a years-wide error and still normalises exactly."""
    typed = datetime(2019, 1, 1, 8, 0, tzinfo=timezone.utc)
    server = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
    station_now = datetime(2019, 1, 1, 10, 0, tzinfo=timezone.utc)

    skew = clock_skew_seconds(station_now, server)
    # Typed two hours before the station's "now", so two hours before server now.
    assert normalize_occurred_at(typed, skew_seconds=skew) == server - timedelta(hours=2)


def test_naive_timestamps_are_read_as_utc_not_rejected():
    naive = datetime(2026, 8, 27, 9, 0)
    assert normalize_occurred_at(naive, skew_seconds=0).tzinfo is timezone.utc


# ── First write ──────────────────────────────────────────────────────────────

def test_first_synced_write_applies():
    d = decide(_in(), None)
    assert d.resolution is Resolution.APPLY
    assert not d.overwrites_foreign_change


def test_first_synced_write_over_an_existing_value_is_flagged():
    """Nothing was synced, yet the row holds something — an upload or a central
    edit. The station's transcription wins, but the overwrite is auditable."""
    d = decide(_in(value="sha256:new"), None, current_value_hash="sha256:old")
    assert d.resolution is Resolution.APPLY
    assert d.overwrites_foreign_change


# ── Same station: version decides, no clock involved ─────────────────────────

def test_newer_version_from_same_station_applies():
    assert decide(_in(version=3), _stored(version=2)).resolution is Resolution.APPLY


def test_out_of_order_retry_from_same_station_is_stale():
    """The failure this prevents: v2 lands, then v1 is retried and resurrects a
    mark the Data Enterer had already corrected."""
    d = decide(_in(version=1, value="sha256:old"), _stored(version=2, value="sha256:new"))
    assert d.resolution is Resolution.STALE
    assert "version 2" in d.reason and "newer" in d.reason


def test_same_version_same_value_is_a_no_op():
    assert decide(_in(version=2), _stored(version=2)).resolution is Resolution.NO_OP


def test_same_version_different_value_is_stale():
    """Same counter, different payload: the counter cannot order them, so the
    stored one stands rather than being overwritten by a coin toss."""
    d = decide(_in(version=2, value="sha256:x"), _stored(version=2, value="sha256:y"))
    assert d.resolution is Resolution.STALE


def test_same_station_ordering_ignores_a_wrong_clock():
    """Version wins over time for one station — which is the point: the station's
    clock may be years out and its counter is still exact."""
    d = decide(_in(version=5, at=T0 - timedelta(days=400)), _stored(version=4, at=LATER))
    assert d.resolution is Resolution.APPLY


# ── Two writers: normalised time decides ─────────────────────────────────────

def test_later_typing_from_another_station_wins():
    d = decide(_in(station="GEITA-1", at=LATER), _stored(station="MWANZA-1", at=T0))
    assert d.resolution is Resolution.APPLY
    assert "MWANZA-1" in d.reason


def test_earlier_typing_from_another_station_is_stale():
    """The lost-update case: a station offline since morning must not replace a
    value another writer recorded later in the day."""
    d = decide(_in(station="GEITA-1", at=T0), _stored(station="MWANZA-1", at=LATER))
    assert d.resolution is Resolution.STALE
    assert "MWANZA-1" in d.reason
    assert "re-enter" in d.reason  # tells the operator what to do about it


def test_simultaneous_different_values_keeps_what_is_stored():
    d = decide(_in(station="GEITA-1", at=T0, value="sha256:x"),
               _stored(station="MWANZA-1", at=T0, value="sha256:y"))
    assert d.resolution is Resolution.STALE
    assert "administrator" in d.reason


def test_simultaneous_same_value_is_a_no_op():
    d = decide(_in(station="GEITA-1", at=T0, value="sha256:same"),
               _stored(station="MWANZA-1", at=T0, value="sha256:same"))
    assert d.resolution is Resolution.NO_OP


# ── Foreign change detection ─────────────────────────────────────────────────

def test_applying_over_a_central_correction_is_flagged_not_blocked():
    """Someone corrected the mark centrally after the last sync. A station entry
    typed *later* still wins — it is the one holding the script — but the fact
    that it replaced a foreign value is reported."""
    d = decide(
        _in(station="GEITA-1", at=LATER, value="sha256:station"),
        _stored(station="MWANZA-1", at=T0, value="sha256:synced"),
        current_value_hash="sha256:corrected_centrally",
    )
    assert d.resolution is Resolution.APPLY
    assert d.overwrites_foreign_change


def test_a_central_correction_is_not_overwritten_by_an_older_entry():
    d = decide(
        _in(station="GEITA-1", at=T0 - timedelta(hours=2), value="sha256:station"),
        _stored(station="MWANZA-1", at=T0, value="sha256:synced"),
        current_value_hash="sha256:corrected_centrally",
    )
    assert d.resolution is Resolution.STALE


def test_unchanged_row_is_not_reported_as_foreign():
    d = decide(_in(version=2), _stored(version=1, value="sha256:aaa"),
               current_value_hash="sha256:aaa")
    assert d.resolution is Resolution.APPLY
    assert not d.overwrites_foreign_change


@pytest.mark.parametrize("resolution", list(Resolution))
def test_every_resolution_is_reachable(resolution):
    """Guards against a rule being added to the enum and never returned."""
    cases = [
        decide(_in(), None),
        decide(_in(version=2), _stored(version=2)),
        decide(_in(version=1), _stored(version=2, value="sha256:b")),
    ]
    assert resolution in {c.resolution for c in cases}
