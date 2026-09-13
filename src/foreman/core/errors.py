"""The error taxonomy the whole system classifies against.

Failures are classified before they are handled. The distinction that matters
most is between :class:`ToolError` and :class:`PolicyViolation`: a tool error is
a conversation with the model, and a policy violation is not negotiable.

See ``docs/architecture.md`` section 7.
"""

from __future__ import annotations

from typing import Literal

__all__ = [
    "BudgetExceeded",
    "ForemanError",
    "PermanentError",
    "PolicyViolation",
    "ToolError",
    "TransientError",
]


class ForemanError(Exception):
    """Base class for every error this system raises on purpose."""


class TransientError(ForemanError):
    """A failure that may succeed if tried again.

    Connection resets, timeouts, 429s and 5xx responses. Retried with backoff
    and jitter, honouring ``Retry-After`` when the server sends one.
    """

    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class PermanentError(ForemanError):
    """A failure that will not succeed if tried again.

    A malformed payload, a missing record, a scope the caller does not hold.
    Retrying wastes budget and hides the real fault behind a slow failure.
    """


class ToolError(ForemanError):
    """A tool ran and failed in a way the model can correct.

    This is feedback, not a stack trace. ``suggestion`` is the part that makes
    the next attempt better, so it is required rather than optional.
    """

    def __init__(
        self,
        message: str,
        *,
        error_type: Literal["validation", "precondition", "not_found", "conflict"],
        suggestion: str,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.suggestion = suggestion

    def as_model_feedback(self) -> str:
        """Render for the model. Never includes internals or a traceback."""
        return f"{self.error_type}: {self} — {self.suggestion}"


# N818: the "Error" suffix is skipped on the next two deliberately. These names
# are documented vocabulary across AGENTS.md, FOREMAN_SPEC.md and architecture.md,
# and the ToolError / PolicyViolation pairing is the point being made.
class PolicyViolation(ForemanError):  # noqa: N818
    """An action was refused by policy.

    Never phrased as advice and never returned to the model as something to fix.
    A model told "you lack the write:orders scope" will try to acquire it.
    """

    def __init__(
        self,
        message: str,
        *,
        rule: str,
        principal: str | None = None,
    ) -> None:
        super().__init__(message)
        self.rule = rule
        self.principal = principal


class BudgetExceeded(ForemanError):  # noqa: N818
    """A spending ceiling would be breached.

    Raised *before* the call is made. A budget discovered after the spend is a
    report, not a control.
    """

    def __init__(
        self,
        message: str,
        *,
        limit_cents: int,
        spent_cents: int,
        scope: Literal["run", "tenant_daily", "global_daily"],
    ) -> None:
        super().__init__(message)
        self.limit_cents = limit_cents
        self.spent_cents = spent_cents
        self.scope = scope
