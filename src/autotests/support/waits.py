"""Explicit waits — the only kind: the implicit wait is 0, so a check for absence is instant.

Wait for what *your* action produces, never for time: no time.sleep in pages or tests.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from selenium.common.exceptions import (
    JavascriptException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait

T = TypeVar("T")

IGNORED = (NoSuchElementException, StaleElementReferenceException)


class Waits:
    def __init__(self, driver: WebDriver, timeout: float, poll: float = 0.1) -> None:
        self.driver = driver
        self.timeout = timeout
        self.poll = poll

    def until(
        self, condition: Callable[[WebDriver], T | None], message: str, timeout: float | None = None
    ) -> T:
        """Until the condition returns something truthy (returned); `message` says what was
        awaited — it is the failure's first line."""
        wait = WebDriverWait(
            self.driver,
            self.timeout if timeout is None else timeout,
            poll_frequency=self.poll,
            ignored_exceptions=IGNORED,
        )
        try:
            # WebDriverWait returns only a truthy result — never the condition's None
            return cast(T, wait.until(condition))
        except TimeoutException as e:
            raise TimeoutException(f"Timed out after {wait._timeout}s waiting for {message}") from e

    def for_new_document(
        self, action: Callable[[], object], message: str = "a new document"
    ) -> None:
        """Runs the action (a submit, a link) and returns once another document replaced this one
        and finished loading — also when the URL stays the same (a form drawn again with errors)."""
        self.driver.execute_script("window.__autotestsDocument = true")
        action()

        def replaced(driver: WebDriver) -> bool:
            try:
                return (
                    driver.execute_script("return window.__autotestsDocument !== true")
                    and driver.execute_script("return document.readyState") == "complete"
                )
            except (JavascriptException, WebDriverException):
                return False  # mid-navigation

        self.until(replaced, message)

    def for_change(self, state: Callable[[], T], action: Callable[[], object], message: str) -> T:
        """Runs the action and returns once `state()` reads something else than before it —
        sorting or paging that may redraw in place or load a new document."""
        before = state()
        action()

        # boxed: a new state that is falsy ("", an empty list) is still a change
        def changed(_: WebDriver) -> tuple[T] | None:
            try:
                now = state()
            except (*IGNORED, JavascriptException):
                return None
            return (now,) if now != before else None

        return self.until(changed, message)[0]
