# lazeims-common

Shared Python package holding **every** LAZEIMS collection validation rule, versioned
contract, natural-key helper, and canonical hashing routine. It is imported by both
`lazeims-central-api` and `lazeims-station` so the rules in Part 2 of the Implementation
Guide are written **exactly once** and can never drift between the two implementations.

## Contents

| Module | Responsibility |
|---|---|
| `enums.py` | All shared enumerations (paper types, attendance sources, incident types, exam phases, filling/display modes, writer modes, rejection codes). |
| `errors.py` | `ValidationError` carrying a stable `RejectionCode`, plus the JSON error-envelope builder. |
| `natural_keys.py` | Build/parse the natural key `exam_code + student_id + subject_code + paper_type + question_number`; student-id rules. |
| `hashing.py` | Deterministic canonical JSON + SHA-256 for reconciliation and snapshot integrity. |
| `schemas/` | Versioned Pydantic contracts: attendance, marks, station package, station sync, collection export. |
| `validation/` | Pure, database-independent rule functions (effective attendance, gating, ranges, completeness, best-N-of-M, topic-weight sum). |

## Design rules

- Every function here is **pure** and database-independent. Central and Station add their
  own persistence/scope checks *around* these functions — never re-implement a rule.
- No blank marks ever: `0` is a valid explicit value; `None`/missing is always rejected.
- Absent students may have no marks at all.
- Effective attendance resolves paper-specific ISAL → subject-wide `ALL` CAL baseline →
  default present (form starting value only).

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```
