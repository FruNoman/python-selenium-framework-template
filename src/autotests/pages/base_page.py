"""Pages: the test talks to a page, never to its elements.

A page declares its URL path and how it knows it is loaded; elements are class attributes
(`autotests.elements`), kept private by convention (`_email`) — the page offers one method per
user action, fluent (`return self`) when the action stays on the page, returning the next page when
it leads there:

    class LoginPage(BasePage):
        path = "login"
        _email = Input(By.ID, "email")
        _submit = Button(By.CSS_SELECTOR, "button[type=submit]")

        def sign_in(self, email: str) -> HomePage:
            self._email.clear_and_type(email)
            self.waits.for_new_document(self._submit.click)
            return HomePage(self.browser)

A page object lives for one test, on the test's browser (`Browser`): no state shared between tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

from selenium.webdriver.remote.webdriver import WebDriver

from autotests.config.settings import Settings
from autotests.elements.core import E, Element
from autotests.support.waits import Waits


@dataclass(frozen=True)
class Browser:
    """One test's browser with what pages need around it."""

    driver: WebDriver
    settings: Settings
    waits: Waits


class BasePage:
    path: str = ""
    """The page's URL relative to base.url (no leading slash); "" for the root."""

    def __init__(self, browser: Browser) -> None:
        self.browser = browser
        self.driver = browser.driver
        self.settings = browser.settings
        self.waits = browser.waits

    def url(self) -> str:
        return self.settings.base.url + self.path

    def is_loaded(self) -> bool:
        """Override with a check of the page's own content when the URL isn't enough."""
        return self.driver.current_url.split("?")[0].startswith(self.url())

    def open(self) -> Self:
        """Navigates to the page and returns once it is loaded."""
        self.driver.get(self.url())
        return self.wait_loaded()

    def get(self) -> Self:
        """Opens the page unless it is the one shown already."""
        return self if self.is_loaded() else self.open()

    def wait_loaded(self) -> Self:
        self.waits.until(lambda _: self.is_loaded(), f"{type(self).__name__} loaded")
        return self

    def element(self, by: str, value: str, name: str, cls: type[E] = Element) -> E:
        """An element found at run time by a locator built then (a row by its text)."""
        element = cls(by, value, name)
        element._parent, element._owner = self, type(self).__name__
        return element

    def js(self, script: str, *args: Any) -> Any:
        """Only where WebDriver has no call for it."""
        return self.driver.execute_script(script, *args)

    def title(self) -> str:
        return self.driver.title
