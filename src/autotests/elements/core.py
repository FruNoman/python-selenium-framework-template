"""The base of the standard elements — Python's `@FindBy`.

An element is declared as a class attribute of a page (or of another element) and is found again
on every use, so a re-rendered DOM never leaves a stale reference behind:

    class LoginPage(BasePage):
        email = Input(By.ID, "email")
        sign_in = Button(By.CSS_SELECTOR, "button[type=submit]")

Access through the page (`self.email`) binds it to the page's browser; `part(...)` finds an
element inside it, `wrap(...)` turns a WebElement found at run time (a row, an option) into one —
every action of all of them is logged as `[Page.field › part] action`.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import TYPE_CHECKING, Any, Self, TypeVar

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

if TYPE_CHECKING:
    from autotests.pages.base_page import BasePage
    from autotests.support.waits import Waits

log = logging.getLogger("autotests.elements")

E = TypeVar("E", bound="Element")

_SPACES = re.compile(r"[\s ]+")


def text_of(element: WebElement) -> str:
    """The text a person reads: textContent with whitespace collapsed (&nbsp; too) — unlike
    `.text` not changed by CSS text-transform, and also for a present but hidden element."""
    return _SPACES.sub(" ", str(element.get_property("textContent") or "")).strip()


def has_class(element: WebElement, name: str) -> bool:
    return name in (element.get_dom_attribute("class") or "").split()


def is_aria_disabled(element: WebElement) -> bool:
    return element.get_dom_attribute("aria-disabled") == "true"


class Element:
    """A part of the page, found by a locator on every use (no wait for presence beyond the
    page's timeout) or wrapping a WebElement found at run time."""

    def __init__(
        self, by: str | None = None, value: str | None = None, name: str | None = None
    ) -> None:
        # private: element classes own the public names (Input.value(), Button.text()…)
        self._by, self._using, self.name = by, value, name
        self._parent: BasePage | Element | None = None
        self._fixed: WebElement | None = None
        self._owner = ""

    # --- declaration: a descriptor on a page or element class

    def __set_name__(self, owner: type, attribute: str) -> None:
        self._owner = owner.__name__
        self.name = self.name or attribute

    def __get__(self, instance: Any, owner: type) -> Self:
        if instance is None:
            return self
        bound = copy.copy(self)
        bound._parent = instance
        return bound

    # --- where it lives

    @property
    def page(self) -> BasePage:
        parent = self._parent
        while isinstance(parent, Element):
            parent = parent._parent
        if parent is None:
            raise RuntimeError(f"{self} is used outside a page: declare it on a page class")
        return parent

    @property
    def driver(self) -> WebDriver:
        return self.page.driver

    @property
    def waits(self) -> Waits:
        return self.page.waits

    def _context(self) -> WebDriver | WebElement:
        return self._parent.root if isinstance(self._parent, Element) else self.driver

    @property
    def root(self) -> WebElement:
        """The WebElement now — found again on every call; waits for it to be present."""
        if self._fixed is not None:
            return self._fixed
        by, using = self._locator()
        return self.waits.until(
            lambda _: self._context().find_element(by, using), f"{self} present"
        )

    def find_all(self) -> list[WebElement]:
        """Every match now — instant, possibly empty."""
        if self._fixed is not None:
            return [self._fixed]
        return self._context().find_elements(*self._locator())

    def _locator(self) -> tuple[str, str]:
        if self._by is None or self._using is None:
            raise TypeError(f"{self} has no locator (a wrapped element is found already)")
        return self._by, self._using

    # --- building parts

    def part(self, by: str, value: str, name: str, cls: type[E] | None = None) -> E:
        """An element inside this one, found on every use."""
        child = (cls or Element)(by, value, name)
        child._parent, child._owner = self, ""
        return child  # type: ignore[return-value]

    def wrap(self, element: WebElement, name: str, cls: type[E] | None = None) -> E:
        """A WebElement found at run time (a row, an option) as an element of this one."""
        child = (cls or Element)(name=name)
        child._parent, child._fixed, child._owner = self, element, ""
        return child  # type: ignore[return-value]

    # --- reading

    def is_present(self) -> bool:
        """In the DOM right now — instant: for optional parts (a pager absent without results)."""
        try:
            return bool(self.find_all()) and self._alive(self.find_all()[0])
        except (NoSuchElementException, StaleElementReferenceException):
            return False

    def is_visible(self) -> bool:
        try:
            return any(e.is_displayed() for e in self.find_all())
        except (NoSuchElementException, StaleElementReferenceException):
            return False

    def text(self) -> str:
        return text_of(self.root)

    def attribute(self, name: str) -> str | None:
        return self.root.get_dom_attribute(name)

    def dom_property(self, name: str) -> Any:
        """A DOM property (value, checked, textContent) — what the page has now, not the HTML."""
        return self.root.get_property(name)

    # --- acting

    def click(self) -> None:
        log.info("[%s] click", self.label)
        root = self.root
        self.waits.until(
            lambda _: root.is_displayed() and root.is_enabled(), f"{self} visible and enabled"
        )
        root.click()

    def scroll_into_view(self) -> Self:
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", self.root)
        return self

    def wait_visible(self) -> Self:
        self.waits.until(lambda _: self.is_visible(), f"{self} visible")
        return self

    def wait_gone(self) -> Self:
        """Until it is hidden or removed."""
        self.waits.until(lambda _: not self.is_visible(), f"{self} gone")
        return self

    def js(self, script: str, *args: Any) -> Any:
        """A script with this element as arguments[0] — only where WebDriver has no call."""
        return self.driver.execute_script(script, self.root, *args)

    # --- naming

    @property
    def label(self) -> str:
        if isinstance(self._parent, Element):
            return f"{self._parent.label} › {self.name}"
        return f"{self._owner}.{self.name}" if self._owner else str(self.name)

    def __repr__(self) -> str:
        return f"{type(self).__name__}[{self.label}]"

    @staticmethod
    def _alive(element: WebElement) -> bool:
        element.tag_name  # noqa: B018 — raises when stale
        return True
