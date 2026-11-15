"""Steps of a test in its log and in the HTML report — what the user does, so a failure says which
step broke:

    def test_LS12_save_order(orders_page, order_data):
        with step("Fill the order"):
            orders_page.fill(order_data)

        with step("Save it"):
            orders_page.save()

            with check:
                assert orders_page.saved_toast() == "Saved", "the toast"

Each step logs `STEP <n>: <title>` to the test's log; a page method may be one too
(`@step("Sign in")`) — a step inside a step is numbered `<n>.<m>`. The plugin puts the test's steps
into the HTML report (passed / failed / a soft check failed) and names the failed step in the
failure's info.
"""

from __future__ import annotations

import logging
import time
from contextlib import ContextDecorator
from dataclasses import dataclass, field
from typing import Literal

from pytest_check import check_log

log = logging.getLogger("autotests")


@dataclass
class Step:
    number: str
    title: str
    status: Literal["running", "passed", "failed", "check failed"] = "running"
    seconds: float = 0.0
    error: str = ""
    _started: float = field(default=0.0, repr=False)
    _checks: int = field(default=0, repr=False)


# the current test's steps — one test at a time per process (xdist runs processes)
_steps: list[Step] = []
_running: list[Step] = []  # the steps open now, outermost first
_counts: list[int] = [0]  # the last number given per depth


def reset() -> None:
    """A new test: no steps yet (the plugin calls it before each test)."""
    _steps.clear()
    _running.clear()
    _counts[:] = [0]


def taken() -> list[Step]:
    """The current test's steps, in the order they started."""
    return list(_steps)


def failed() -> Step | None:
    """The innermost step that failed — where the test broke."""
    broken = [s for s in _steps if s.status == "failed"]
    return max(broken, key=lambda s: s.number.count(".")) if broken else None


class _StepBlock(ContextDecorator):
    def __init__(self, title: str) -> None:
        self.title = title

    def __enter__(self) -> Step:
        _counts[-1] += 1
        number = f"{_running[-1].number}.{_counts[-1]}" if _running else str(_counts[-1])
        current = Step(number, self.title, _started=time.monotonic())
        current._checks = len(check_log.get_failures())
        _steps.append(current)
        _running.append(current)
        _counts.append(0)
        log.info("STEP %s: %s", number, self.title)
        return current

    def __exit__(self, _kind: object, error: BaseException | None, _tb: object) -> None:
        _counts.pop()
        current = _running.pop()
        current.seconds = time.monotonic() - current._started
        if error is not None:
            current.status = "failed"
            current.error = str(error).splitlines()[0] if str(error) else type(error).__name__
            log.info("STEP %s failed: %s — %s", current.number, current.title, current.error)
        elif len(check_log.get_failures()) > current._checks:
            current.status = "check failed"
        else:
            current.status = "passed"


def step(title: str) -> _StepBlock:
    """`with step("<what the user does>"):` around a test's step, or `@step("…")` on a page
    method."""
    return _StepBlock(title)
