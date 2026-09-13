"""The error taxonomy.

Classification is the point of this module: the handling code decides what to
do by *type*, so the distinctions have to hold. The one that matters most is
ToolError vs PolicyViolation — the first is a conversation with the model, the
second is not negotiable.
"""

from __future__ import annotations

import pytest

from foreman.core.errors import (
    BudgetExceeded,
    ForemanError,
    PermanentError,
    PolicyViolation,
    ToolError,
    TransientError,
)

ALL_ERRORS = [
    TransientError,
    PermanentError,
    ToolError,
    PolicyViolation,
    BudgetExceeded,
]


@pytest.mark.parametrize("error_type", ALL_ERRORS)
def test_every_error_is_catchable_as_one_family(error_type: type[ForemanError]) -> None:
    """A caller that wants "anything we raised on purpose" can catch one type."""
    assert issubclass(error_type, ForemanError)


def test_foreman_errors_do_not_swallow_unrelated_exceptions() -> None:
    assert not issubclass(ValueError, ForemanError)


class TestTransientError:
    def test_retry_after_is_optional(self) -> None:
        assert TransientError("connection reset").retry_after_seconds is None

    def test_retry_after_is_preserved(self) -> None:
        """A server that says when to come back knows more than a backoff curve."""
        assert TransientError("429", retry_after_seconds=2.5).retry_after_seconds == 2.5


class TestToolError:
    def test_carries_its_classification_and_suggestion(self) -> None:
        err = ToolError(
            "quantity must be positive",
            error_type="validation",
            suggestion="you passed -5; send a positive integer",
        )
        assert err.error_type == "validation"
        assert err.suggestion == "you passed -5; send a positive integer"

    def test_suggestion_is_required_not_optional(self) -> None:
        """The part that makes the next attempt better is not optional."""
        with pytest.raises(TypeError):
            ToolError("boom", error_type="validation")  # type: ignore[call-arg]

    def test_model_feedback_includes_the_suggestion(self) -> None:
        err = ToolError(
            "no such purchase order",
            error_type="not_found",
            suggestion="check the PO number",
        )
        feedback = err.as_model_feedback()
        assert "not_found" in feedback
        assert "no such purchase order" in feedback
        assert "check the PO number" in feedback

    def test_model_feedback_is_a_single_line(self) -> None:
        """It goes into a prompt, so it must not carry a traceback."""
        err = ToolError("failed", error_type="conflict", suggestion="retry with the new version")
        assert "\n" not in err.as_model_feedback()


class TestPolicyViolation:
    def test_records_the_rule_that_refused(self) -> None:
        err = PolicyViolation("write exceeds ceiling", rule="WRITE_CEILING_V2")
        assert err.rule == "WRITE_CEILING_V2"

    def test_principal_is_optional(self) -> None:
        assert PolicyViolation("refused", rule="R1").principal is None

    def test_principal_is_recorded_when_known(self) -> None:
        err = PolicyViolation("refused", rule="R1", principal="agent:extractor")
        assert err.principal == "agent:extractor"

    def test_has_no_model_feedback_method(self) -> None:
        """Deliberate: a refusal phrased as advice invites a workaround."""
        assert not hasattr(PolicyViolation("refused", rule="R1"), "as_model_feedback")


class TestBudgetExceeded:
    def test_records_which_ceiling_broke(self) -> None:
        err = BudgetExceeded("over budget", limit_cents=10, spent_cents=11, scope="run")
        assert (err.scope, err.limit_cents, err.spent_cents) == ("run", 10, 11)

    @pytest.mark.parametrize("scope", ["run", "tenant_daily", "global_daily"])
    def test_every_documented_scope_is_accepted(self, scope: str) -> None:
        err = BudgetExceeded("over", limit_cents=1, spent_cents=2, scope=scope)  # type: ignore[arg-type]
        assert err.scope == scope
