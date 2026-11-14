"""What a test reports beyond pass/fail, without a browser: a known bug scoped to one check."""

from __future__ import annotations

import pytest
from pytest_check import check, check_log

from autotests.known_bug import known_bug

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
