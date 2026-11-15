"""What a test reports beyond pass/fail, without a browser: a known bug scoped to one check, the
test's steps."""

from __future__ import annotations

import logging

import pytest
from pytest_check import check, check_log

from autotests import step as test_steps
from autotests.known_bug import known_bug
from autotests.step import step

# --- known bug


def test_a_known_bug_that_reproduces_is_an_xfail() -> None:
    total = "100.00"

    with (
        pytest.raises(pytest.xfail.Exception, match="BUG-1: the total ignores the discount"),
        known_bug("BUG-1: the total ignores the discount"),
    ):
        assert total == "90.00", "the total with the discount"


def test_a_known_bug_seen_by_a_soft_check_is_an_xfail_and_not_a_failed_check() -> None:
    toast = ""
    failures_before = len(check_log.get_failures())

    with pytest.raises(pytest.xfail.Exception), known_bug("BUG-2: the toast is missing"), check:
        assert toast == "Saved", "the toast"

    assert len(check_log.get_failures()) == failures_before, "the bug's check isn't the test's"


def test_a_known_bug_that_no_longer_reproduces_fails_the_test() -> None:
    total = "90.00"

    with (
        pytest.raises(pytest.fail.Exception, match="known bug BUG-3 no longer reproduces"),
        known_bug("BUG-3: the total ignores the discount"),
    ):
        assert total == "90.00", "the total with the discount"


# --- steps


@step("Sign in")
def _sign_in() -> None:
    with step("Type the password"):
        pass


def test_steps_are_numbered_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    test_steps.reset()

    with step("Open the form"):
        _sign_in()
    with step("Save it"):
        pass

    with check:
        assert [(s.number, s.title) for s in test_steps.taken()] == [
            ("1", "Open the form"),
            ("1.1", "Sign in"),
            ("1.1.1", "Type the password"),
            ("2", "Save it"),
        ], "a step inside a step is <n>.<m>; a decorated page method is a step"
    with check:
        assert "STEP 1.1: Sign in" in caplog.text, "each step in the test's log"
    with check:
        assert {s.status for s in test_steps.taken()} == {"passed"}, "all passed"


def test_the_failed_step_is_the_innermost_one_that_broke() -> None:
    test_steps.reset()

    with pytest.raises(AssertionError), step("Save the order"), step("Confirm"):
        raise AssertionError("the dialog stayed open")
    broken = test_steps.failed()

    assert broken is not None, "a step failed"
    assert (broken.number, broken.error) == ("1.1", "the dialog stayed open"), "the innermost one"
    test_steps.reset()  # this test's own report shows no step failed on purpose
