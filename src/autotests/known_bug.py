"""A known product bug scoped to the one check it breaks — inside a test, around that check only:

    def test_LS12_save_order(orders_page, orders_texts):
        orders_page.save()

        with check:
            assert orders_page.saved_toast() == orders_texts.saved, "the toast"

        with known_bug("LS-345: the total ignores the discount"):
            assert orders_page.total() == "90.00", "the total with the discount"

The block failing (an assertion, a soft check, a wait timing out) is the bug: the test reports
XFAIL with the reason and stops there; the checks before it ran and still count — one of them
failed turns the test red. The block passing turns the test red: the bug no longer reproduces,
remove the mark (strict, like `xfail(strict=True)`). A failure outside the block stays a failure.

The whole-test `@pytest.mark.xfail(strict=True, reason=…)` only when the bug blocks the test's
start (its entry page or its precondition fails).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from pytest_check import check_log

log = logging.getLogger("autotests")


@contextmanager
def known_bug(reason: str) -> Iterator[None]:
    """`reason` = "<KEY>: <why>" — the tracker's key first, it names the bug in the messages."""
    key = reason.split(":", 1)[0].strip()
    # soft checks (pytest-check) inside the block log their failures instead of raising: the ones
    # it added are the bug's, taken out of the test's own
    failures = check_log.get_failures()
    before = len(failures)
    failure: str | None = None
    try:
        yield
    except Exception as e:
        failure = str(e).splitlines()[0] if str(e) else type(e).__name__
    if len(failures) > before:
        failure = failure or failures[before].splitlines()[0].removeprefix("FAILURE: ")
        check_log._num_failures -= len(failures) - before
        del failures[before:]
    if failure is None:
        pytest.fail(f"known bug {key} no longer reproduces — remove the mark ({reason})")
    log.info("known bug %s reproduced: %s", key, failure)
    pytest.xfail(reason)
