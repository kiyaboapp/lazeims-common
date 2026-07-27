"""Error types and the canonical JSON error envelope.

A single exception type (:class:`ValidationError`) carries a stable
:class:`~lazeims_common.enums.RejectionCode`. Both Central (HTTP responses) and
Station (sync-event results) translate this one type into their own transport,
so the *reason* a value was rejected is defined in exactly one place.
"""

from __future__ import annotations

from typing import Any

from .enums import RejectionCode


class LazeimsError(Exception):
    """Base for all package errors."""


class ValidationError(LazeimsError):
    """Raised when a domain rule is violated.

    Parameters
    ----------
    code:
        A stable machine-readable rejection code.
    message:
        A human-readable, actionable message.
    details:
        Optional structured context (e.g. offending question numbers, the
        computed vs. allowed maximum). Must be JSON-serialisable.
    """

    def __init__(
        self,
        code: RejectionCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"{code.value}: {message}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
        }


def error_envelope(
    code: RejectionCode,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build the canonical API error envelope.

    Shape (matches §8.1 of the delivery plan)::

        {"error": {"code", "message", "details", "request_id"}}
    """

    return {
        "error": {
            "code": code.value,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }


def envelope_from_exc(
    exc: ValidationError, request_id: str | None = None
) -> dict[str, Any]:
    """Convenience: build an error envelope directly from a ValidationError."""
    return error_envelope(exc.code, exc.message, exc.details, request_id)
