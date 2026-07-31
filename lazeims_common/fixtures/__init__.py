"""Shared contract fixtures asserted by more than one repository (§12).

Shipped in the package rather than kept under ``tests/`` because backend-sis
imports them from its own test suite (D6): ``lazeims-common`` is a test-only
dependency there, and a fixture that only exists inside another repo's test
directory cannot be imported.
"""

from __future__ import annotations

from . import exametrics

__all__ = ["exametrics"]
