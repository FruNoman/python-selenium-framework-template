"""Buttons, text fields, checkboxes, radio groups, file uploads, dates."""

from __future__ import annotations

import contextlib
import datetime as dt
from collections.abc import Callable
from pathlib import Path
from typing import Self

from pydantic import SecretStr
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.file_detector import LocalFileDetector
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from autotests.elements.core import Element, log, text_of


def _plain(text: str | SecretStr) -> str:
    return text.get_secret_value() if isinstance(text, SecretStr) else text


def _shown(text: str | SecretStr) -> str:
    return "***" if isinstance(text, SecretStr) else text


class Button(Element):
    """`<button>`, input[type=button|submit], a link or role=button. Disabled = `disabled` or
    aria-disabled=true; busy = aria-busy=true (a spinner while its request runs)."""

    def click(self) -> None:
        """Waits until the button is enabled (forms often enable it after validation), clicks."""
        log.info("[%s] click", self.label)
        self.waits.until(lambda _: self.is_enabled(), f"{self} enabled")
        self.root.click()

    def click_and_wait_idle(self) -> None:
        """Clicks and waits until it is enabled and not busy again ("Saving…")."""
        self.click()
        self.waits.until(lambda _: self.is_enabled() and not self.is_busy(), f"{self} idle")

    def click_until(self, what: str, done: Callable[[WebDriver], bool]) -> None:
        """Clicks until `done` holds — for a click the app can lose: a React button right after a
        typed value, one covered for a moment (a toast, a sticky header) or not drawn yet."""
        log.info("[%s] click until %s", self.label, what)

        def clicked(driver: WebDriver) -> bool:
            if done(driver):
                return True
            root = self.root
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", root)
            try:
                root.click()
            except (ElementNotInteractableException, ElementClickInterceptedException):
                return False
            return done(driver)

        self.waits.until(clicked, f"{self} until {what}")

    def is_enabled(self) -> bool:
        root = self.root
        return root.is_enabled() and root.get_dom_attribute("aria-disabled") != "true"

    def is_busy(self) -> bool:
        return self.attribute("aria-busy") == "true"


class Input(Element):
    """A text field: any input that takes typing, or a textarea. Its error is found through ARIA
    (aria-errormessage / aria-describedby), the way a screen reader finds it."""

    def type(self, text: str | SecretStr) -> Self:
        """Types after what's there already. A `SecretStr` (a password) is logged as ***."""
        log.info("[%s] type '%s'", self.label, _shown(text))
        self.root.send_keys(_plain(text))
        return self

    def clear_and_type(self, text: str | SecretStr) -> Self:
        log.info("[%s] clear and type '%s'", self.label, _shown(text))
        root = self.root
        root.clear()
        root.send_keys(_plain(text))
        return self

    def type_kept(self, text: str) -> Self:
        """Types and returns once the field keeps the text over two reads, typing again when it
        lost it — a field the app draws again while it is typed into (React)."""
        log.info("[%s] type (kept) '%s'", self.label, text)
        kept_once = [False]

        def kept(_: WebDriver) -> bool:
            if self.value() != text:
                kept_once[0] = False
                root = self.root
                root.clear()
                root.send_keys(text)
                return False
            was, kept_once[0] = kept_once[0], True
            return was

        self.waits.until(kept, f"{self} keeps '{text}'")
        return self

    def blur(self) -> Self:
        """Leaves the field (Tab) — fires blur validation."""
        self.root.send_keys(Keys.TAB)
        return self

    def value(self) -> str:
        """The current value — the `value` property, what was typed."""
        return str(self.root.get_property("value") or "")

    def error(self) -> str:
        """Text of the visible error linked by aria-errormessage / aria-describedby, "" if none."""
        root = self.root
        ids = " ".join(
            filter(
                None,
                (
                    root.get_dom_attribute("aria-errormessage"),
                    root.get_dom_attribute("aria-describedby"),
                ),
            )
        ).split()
        for element_id in ids:
            for element in self.driver.find_elements(By.ID, element_id):
                if element.is_displayed() and text_of(element):
                    return text_of(element)
        return ""

    def is_invalid(self) -> bool:
        """aria-invalid=true, or the browser's own constraint validation fails."""
        root = self.root
        return root.get_dom_attribute("aria-invalid") == "true" or bool(
            root.get_property("validationMessage")
        )

    def is_read_only(self) -> bool:
        return bool(self.root.get_property("readOnly"))


def _is_native(element: WebElement) -> bool:
    return element.tag_name == "input"


class CheckBox(Element):
    """Anything on/off: input[type=checkbox], role=checkbox / role=switch (aria-checked), or a
    wrapper (a label, a component) with one of those inside."""

    def check(self) -> Self:
        return self.set_checked(True)

    def uncheck(self) -> Self:
        return self.set_checked(False)

    def set_checked(self, checked: bool) -> Self:
        """Clicks only when the state differs, after waiting until enabled; waits for the state."""
        if self.is_checked() == checked:
            return self
        log.info("[%s] %s", self.label, "check" if checked else "uncheck")
        self.waits.until(lambda _: self.is_enabled(), f"{self} enabled")
        self._click_target().click()
        self.waits.until(
            lambda _: self.is_checked() == checked,
            f"{self} {'checked' if checked else 'unchecked'}",
        )
        return self

    def is_checked(self) -> bool:
        box = self._box()
        return (
            box.is_selected()
            if _is_native(box)
            else box.get_dom_attribute("aria-checked") == "true"
        )

    def is_indeterminate(self) -> bool:
        """ "Some but not all": a native box's indeterminate, or aria-checked=mixed."""
        box = self._box()
        return (
            bool(box.get_property("indeterminate"))
            if _is_native(box)
            else (box.get_dom_attribute("aria-checked") == "mixed")
        )

    def is_enabled(self) -> bool:
        box = self._box()
        return box.is_enabled() and box.get_dom_attribute("aria-disabled") != "true"

    def label_text(self) -> str:
        """Its accessible name — the <label> of a native box, the text of an ARIA one."""
        return self._box().accessible_name

    def _box(self) -> WebElement:
        root = self.root
        if _is_native(root) or root.get_dom_attribute("aria-checked") is not None:
            return root
        inner = root.find_elements(By.CSS_SELECTOR, "input[type=checkbox], [aria-checked]")
        return inner[0] if inner else root

    def _click_target(self) -> WebElement:
        # the box, or — a styled box whose input is 0 px (React grids) — its label, else the
        # nearest ancestor with a size
        box = self._box()
        if box.is_displayed() and box.size["height"] > 0 and box.size["width"] > 0:
            return box
        box_id = box.get_dom_attribute("id")
        if box_id:
            labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{box_id}']")
            if labels and labels[0].is_displayed():
                return labels[0]
        ancestor = box
        for _ in range(5):
            ancestor = ancestor.find_element(By.XPATH, "..")
            if ancestor.size["height"] > 0 and ancestor.size["width"] > 0:
                return ancestor
        return box


class RadioGroup(Element):
    """A group of radios, declared on its container: native input[type=radio] or role=radiogroup
    with role=radio items. An option is addressed by value or label — native: value / its label;
    ARIA: data-value / its text."""

    def select(self, value_or_label: str) -> Self:
        radio = self._find(value_or_label)
        if not self._enabled(radio):
            raise ValueError(f"Option '{value_or_label}' of {self} is disabled")
        log.info("[%s] select '%s'", self.label, value_or_label)
        radio.click()
        self.waits.until(lambda _: self._checked(radio), f"{self} '{value_or_label}' checked")
        return self

    def selected(self) -> str:
        """Label of the checked option, "" when none."""
        return next((self._label(r) for r in self._radios() if self._checked(r)), "")

    def selected_value(self) -> str:
        return next((self._value(r) for r in self._radios() if self._checked(r)), "")

    def options(self) -> list[str]:
        return [self._label(r) for r in self._radios()]

    def is_option_enabled(self, value_or_label: str) -> bool:
        return self._enabled(self._find(value_or_label))

    def _radios(self) -> list[WebElement]:
        return self.root.find_elements(By.CSS_SELECTOR, "input[type=radio], [role=radio]")

    def _find(self, value_or_label: str) -> WebElement:
        for radio in self._radios():
            if value_or_label in (self._value(radio), self._label(radio)):
                return radio
        raise ValueError(f"No option '{value_or_label}' in {self}, options: {self.options()}")

    @staticmethod
    def _label(radio: WebElement) -> str:
        return radio.accessible_name if _is_native(radio) else text_of(radio)

    @classmethod
    def _value(cls, radio: WebElement) -> str:
        if _is_native(radio):
            return str(radio.get_property("value") or "")
        return radio.get_dom_attribute("data-value") or cls._label(radio)

    @staticmethod
    def _checked(radio: WebElement) -> bool:
        return (
            radio.is_selected()
            if _is_native(radio)
            else (radio.get_dom_attribute("aria-checked") == "true")
        )

    @staticmethod
    def _enabled(radio: WebElement) -> bool:
        return radio.is_enabled() and radio.get_dom_attribute("aria-disabled") != "true"


class FileUpload(Element):
    """input[type=file] — declared on the input itself, also when a styled button hides it. Files
    go in through send_keys, no OS dialog; a hidden input is shown for the moment of the upload. On
    a Grid the files are sent to the node first."""

    _SHOW = (
        "const e = arguments[0]; if (e.checkVisibility()) return null;"
        " const was = {hidden: e.hidden, style: e.getAttribute('style')}; e.hidden = false;"
        " e.style.cssText += ';display:block !important;visibility:visible !important;"
        "opacity:1 !important;width:1px;height:1px'; return was"
    )
    _RESTORE = (
        "const e = arguments[0], was = arguments[1]; e.hidden = was.hidden;"
        " if (was.style === null) e.removeAttribute('style');"
        " else e.setAttribute('style', was.style)"
    )

    def upload(self, *files: Path | str) -> Self:
        log.info("[%s] upload %s", self.label, [Path(f).name for f in files])
        with contextlib.suppress(WebDriverException):  # a local driver needs none
            self.driver.file_detector = LocalFileDetector()
        root = self.root
        hidden = self.driver.execute_script(self._SHOW, root)
        try:
            root.send_keys("\n".join(str(Path(f).resolve()) for f in files))
        finally:
            if hidden is not None:
                self.driver.execute_script(self._RESTORE, root, hidden)
        return self

    def file_names(self) -> list[str]:
        return self.js("return Array.from(arguments[0].files).map(f => f.name)")


class Calendar(Element):
    """A date field: a native input[type=date] (set in ISO through the DOM — typed keys mean
    different dates in different browser locales), or a picker: an input opening a role=grid of
    days carrying data-date=YYYY-MM-DD, with previous/next month buttons (aria-label "Prev…" /
    "Next…"). Another picker: override the CSS hooks."""

    grid_css = "[role=grid]"
    prev_css = "[aria-label^=Prev], [aria-label^=prev]"
    next_css = "[aria-label^=Next], [aria-label^=next]"

    def day_css(self, date: dt.date) -> str:
        return f"[data-date='{date.isoformat()}']"

    def pick(self, date: dt.date) -> Self:
        log.info("[%s] pick %s", self.label, date)
        if self._is_native():
            self.js(
                "arguments[0].value = arguments[1];"
                " arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
                " arguments[0].dispatchEvent(new Event('change', {bubbles: true}))",
                date.isoformat(),
            )
            return self
        self.open()
        target = (date.year, date.month)
        for _ in range(1200):
            shown = self.displayed_month()
            if shown == target:
                break
            css = self.prev_css if target < shown else self.next_css
            self.root.find_element(By.CSS_SELECTOR, css).click()
            self.waits.until(
                lambda _, s=shown: self.displayed_month() != s, f"{self} leaves {shown}"
            )
        self.root.find_element(By.CSS_SELECTOR, f"{self.grid_css} {self.day_css(date)}").click()
        self.waits.until(lambda _: not self.is_open(), f"{self} closed after picking {date}")
        return self

    def value(self) -> str:
        return str(self._input().get_property("value") or "")

    def open(self) -> Self:
        if not self._is_native() and not self.is_open():
            self._input().click()
            self.waits.until(lambda _: self.is_open(), f"{self} open")
        return self

    def is_open(self) -> bool:
        grids = self.root.find_elements(By.CSS_SELECTOR, self.grid_css)
        return bool(grids) and grids[0].is_displayed()

    def displayed_month(self) -> tuple[int, int]:
        """The month on screen, from the day in the middle of the grid (padding days from the
        neighbouring months never sit there)."""
        grids = self.root.find_elements(By.CSS_SELECTOR, self.grid_css)
        days = grids[0].find_elements(By.CSS_SELECTOR, "[data-date]") if grids else []
        if not days:
            raise RuntimeError(f"{self} shows no days with data-date")
        year, month = (days[len(days) // 2].get_dom_attribute("data-date") or "")[:7].split("-")
        return int(year), int(month)

    def _is_native(self) -> bool:
        root = self.root
        return root.tag_name == "input" and root.get_dom_attribute("type") == "date"

    def _input(self) -> WebElement:
        root = self.root
        return root if root.tag_name == "input" else root.find_element(By.TAG_NAME, "input")
