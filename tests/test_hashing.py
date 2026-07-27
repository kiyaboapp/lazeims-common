from __future__ import annotations

from decimal import Decimal

from lazeims_common.enums import PaperType
from lazeims_common.hashing import (
    canonical_json,
    sha256_hex,
    sha256_prefixed,
)


def test_canonical_json_sorts_keys():
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonical_json_no_whitespace():
    assert canonical_json({"a": [1, 2, 3]}) == '{"a":[1,2,3]}'


def test_canonical_json_order_independent_hash():
    a = {"x": 1, "y": {"m": 2, "n": 3}}
    b = {"y": {"n": 3, "m": 2}, "x": 1}
    assert sha256_hex(a) == sha256_hex(b)


def test_decimal_is_deterministic():
    # 1.0 and 1.00 normalise to the same canonical form
    assert canonical_json(Decimal("1.0")) == canonical_json(Decimal("1.00"))


def test_enum_serialised_by_value():
    assert canonical_json({"p": PaperType.THEORY1}) == '{"p":"THEORY1"}'


def test_sha256_prefixed_format():
    h = sha256_prefixed({"a": 1})
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64


def test_non_ascii_preserved():
    assert canonical_json({"name": "Müller"}) == '{"name":"Müller"}'
