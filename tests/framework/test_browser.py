"""The framework's own wiring in a browser — on about:blank, no app needed. A project drops
tests/framework once its TMS cases cover these layers."""

from __future__ import annotations

from pathlib import Path

from pytest_check import check

from autotests.pages.base_page import Browser
from autotests.support import artifacts
from tests.framework.pages import BlankPage, ReactQuirksPage


def test_a_test_starts_with_a_fresh_browser(browser: Browser) -> None:
    blank_page = BlankPage(browser).open()

    assert len(browser.driver.window_handles) == 1, "only this test's window"
    blank_page.js("window.open('about:blank')")  # left open: the next test must not see it


def test_another_test_starts_with_a_fresh_browser_too(browser: Browser) -> None:
    BlankPage(browser).open()

    assert len(browser.driver.window_handles) == 1, "no window of another test"


def test_standard_elements_cope_with_react_rerenders(browser: Browser) -> None:
    react_quirks_page = ReactQuirksPage(browser).open().draw().wait_toast_gone()

    react_quirks_page.quantity.type_kept("3")
    quantity = react_quirks_page.quantity.value()

    react_quirks_page.next_button.click_until(
        "the next step", lambda _: react_quirks_page.step() != "Define"
    )
    step = react_quirks_page.step()

    react_quirks_page.box.check()
    checked = react_quirks_page.box.is_checked()

    with check:
        assert quantity == "3", "type_kept: the field drawn again keeps the text"
    with check:
        assert step != "Define", "click_until: the ignored first click clicked again"
    with check:
        assert checked, "a 0 px checkbox checked through its cell"


def test_failure_artifacts_capture_the_browser(browser: Browser, tmp_path: Path) -> None:
    BlankPage(browser).open().js(
        "document.body.innerHTML = '<h1>evidence</h1>'; console.error('boom')"
    )

    folder = artifacts.save(browser.driver, tmp_path / "case", "tests/x.py::test_y", "it failed")

    with check:
        assert (folder / "screenshot.png").stat().st_size > 0, "screenshot"
    with check:
        assert "evidence" in (folder / "page.html").read_text(), "the DOM"
    with check:
        assert "boom" in (folder / "console.log").read_text(), "the browser console"
    with check:
        assert "failure:  it failed" in (folder / "info.txt").read_text(), "info"
