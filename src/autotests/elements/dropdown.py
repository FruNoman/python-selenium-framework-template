"""Dropdowns — one interface whatever they are built from: a native <select>, a button with a
ul/li menu, an ARIA combobox with a listbox (a portal too), checkboxes in a panel, react-select."""

from __future__ import annotations

from typing import Protocol, Self

from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.select import Select

from autotests.elements.core import Element, has_class, is_aria_disabled, log, text_of


class Dropdown(Protocol):
    """A single-choice dropdown. Pages declare the concrete class; code that only picks a value
    can take this protocol."""

    def select(self, text: str) -> Self: ...
    def selected(self) -> str: ...
    def options(self) -> list[str]: ...
    def open(self) -> Self: ...
    def close(self) -> Self: ...
    def is_open(self) -> bool: ...


class SelectDropdown(Element):
    """Native <select>. Texts are textContent (CSS text-transform doesn't change them). The browser
    draws the open list, so open/close do nothing. A select that navigates on change: wrap
    `select` in `waits.for_new_document`."""

    def select(self, text: str) -> Self:
        if not self.is_option_enabled(text):
            raise ValueError(f"Option '{text}' of {self} is disabled")
        log.info("[%s] select '%s'", self.label, text)
        Select(self.root).select_by_visible_text(text)
        return self

    def select_by_value(self, value: str) -> Self:
        Select(self.root).select_by_value(value)
        return self

    def selected(self) -> str:
        chosen = Select(self.root).all_selected_options
        return text_of(chosen[0]) if chosen else ""

    def selected_value(self) -> str:
        """`value` of the chosen option — what the form submits."""
        return self.root.get_property("value") or ""

    def options(self) -> list[str]:
        return [text_of(o) for o in Select(self.root).options]

    def is_option_enabled(self, text: str) -> bool:
        for option in Select(self.root).options:
            if text_of(option) == text:
                return option.is_enabled()
        raise ValueError(f"No option '{text}' in {self}, options: {self.options()}")

    def open(self) -> Self:
        return self

    def close(self) -> Self:
        return self

    def is_open(self) -> bool:
        return False


class ListDropdown(Element):
    """The classic dropdown: a toggle button and a ul/li menu under it, declared on the element
    holding both. Dividers and empty items aren't options; disabled = class "disabled",
    aria-disabled=true or a disabled link/button; chosen = the item marked active / selected /
    aria-selected=true, else the toggle's text. Other markup: override the CSS hooks."""

    toggle_css = "button, [aria-haspopup], [data-toggle]"
    menu_css = "ul, [role=menu], [role=listbox]"

    def select(self, text: str) -> Self:
        self.open()
        item = self._item(text)
        if self._disabled(item):
            raise ValueError(f"Option '{text}' of {self} is disabled")
        log.info("[%s] select '%s'", self.label, text)
        links = item.find_elements(By.CSS_SELECTOR, "a, button")
        (links[0] if links else item).click()
        self.waits.until(
            lambda _: not self.is_open() and self.selected() == text,
            f"{self} closed with '{text}' chosen",
        )
        return self

    def selected(self) -> str:
        for li in self._items():
            if (
                has_class(li, "active")
                or has_class(li, "selected")
                or li.get_dom_attribute("aria-selected") == "true"
            ):
                return text_of(li)
        return text_of(self._toggle())

    def options(self) -> list[str]:
        return [text_of(li) for li in self._items()]

    def is_option_enabled(self, text: str) -> bool:
        return not self._disabled(self._item(text))

    def open(self) -> Self:
        if not self.is_open():
            self._toggle().click()
            self.waits.until(lambda _: self.is_open(), f"{self} open")
        return self

    def close(self) -> Self:
        if self.is_open():
            self._toggle().click()
            self.waits.until(lambda _: not self.is_open(), f"{self} closed")
        return self

    def is_open(self) -> bool:
        menu = self._menu()
        return menu is not None and menu.is_displayed()

    def _toggle(self) -> WebElement:
        return self.root.find_element(By.CSS_SELECTOR, self.toggle_css)

    def _menu(self) -> WebElement | None:
        menus = self.root.find_elements(By.CSS_SELECTOR, self.menu_css)
        return menus[0] if menus else None

    def _items(self) -> list[WebElement]:
        menu = self._menu()
        items = menu.find_elements(By.TAG_NAME, "li") if menu else []
        return [
            li
            for li in items
            if not has_class(li, "divider")
            and li.get_dom_attribute("role") != "separator"
            and text_of(li)
        ]

    def _item(self, text: str) -> WebElement:
        for li in self._items():
            if text_of(li) == text:
                return li
        raise ValueError(f"No option '{text}' in {self}, options: {self.options()}")

    @staticmethod
    def _disabled(li: WebElement) -> bool:
        return (
            has_class(li, "disabled")
            or is_aria_disabled(li)
            or bool(li.find_elements(By.CSS_SELECTOR, "[disabled], [aria-disabled=true]"))
        )


class AriaDropdown(Element):
    """ARIA combobox (WAI-ARIA 1.2): an input with role=combobox and aria-expanded; its options
    (role=option) in the listbox aria-controls names — found by id, so one rendered into <body>
    (a portal: MUI, Ant Design, most React/Vue kits) works the same. Declared on the element holding
    the input, or on the input itself.

    Searchable and async: `search` returns once the options listed are for exactly the typed text —
    an earlier prefix's response can arrive last. The signal: the root's data-state
    (loading|loaded|empty) + data-query when it has them, else "expanded and the listbox not
    aria-busy"; override `results_shown_for` for another. Option label = data-label, else text."""

    _LISTBOX = (
        "const input = arguments[0].matches('[role=combobox]') ? arguments[0] :"
        " arguments[0].querySelector('[role=combobox]'); const listbox ="
        " document.getElementById(input.getAttribute('aria-controls') ||"
        " input.getAttribute('aria-owns')); const options = listbox ?"
        " Array.from(listbox.querySelectorAll('[role=option]')) : [];"
        " const label = o => (o.dataset.label || o.textContent).trim();"
    )

    def search(self, text: str) -> Self:
        """Types into the emptied input; returns once the options listed are for that text."""
        log.info("[%s] search '%s'", self.label, text)
        field = self._input()
        field.click()
        field.clear()
        field.send_keys(text)
        self.waits.until(lambda _: self.results_shown_for(text), f"options of {self} for '{text}'")
        return self

    def select(self, text: str) -> Self:
        """Picks the option labelled `text`: from the open list if it's there, else searches."""
        if not (self.is_open() and text in self.options()):
            self.search(text)
        option = self.js(
            self._LISTBOX + " return options.find(o => label(o) === arguments[1]) || null", text
        )
        if option is None:
            raise ValueError(f"No option '{text}' in {self}, listed: {self.options()}")
        log.info("[%s] select '%s'", self.label, text)
        option.click()
        self._wait_chosen(text)
        return self

    def select_with_keyboard(self, query: str, text: str) -> Self:
        """Picks `text` with ↓ … Enter among the options for `query` — the keyboard path."""
        self.search(query)
        field = self._input()
        for _ in range(len(self.options())):
            field.send_keys(Keys.ARROW_DOWN)
            if self._active_option() == text:
                field.send_keys(Keys.ENTER)
                self._wait_chosen(text)
                return self
        raise ValueError(f"No option '{text}' in {self} for '{query}'")

    def selected(self) -> str:
        """The text in the input — the chosen option's label once one is chosen."""
        return self._input().get_property("value") or ""

    def options(self) -> list[str]:
        return self.js(self._LISTBOX + " return options.map(label)")

    def has_no_matches(self) -> bool:
        return self.is_open() and not self.options()

    def open(self) -> Self:
        if not self.is_open():
            self._input().click()
            self.waits.until(lambda _: self.is_open(), f"{self} open")
        return self

    def close(self) -> Self:
        if self.is_open():
            self._input().send_keys(Keys.ESCAPE)
            self.waits.until(lambda _: not self.is_open(), f"{self} closed")
        return self

    def is_open(self) -> bool:
        return self._input().get_dom_attribute("aria-expanded") == "true"

    def results_shown_for(self, text: str) -> bool:
        """Whether the options listed now belong to `text`."""
        return bool(
            self.js(
                self._LISTBOX + " const root = arguments[0]; if (root.dataset.state !== undefined)"
                " return root.dataset.query === arguments[1] && (root.dataset.state === 'loaded' ||"
                " root.dataset.state === 'empty'); return input.getAttribute('aria-expanded') ==="
                " 'true' && !!listbox && listbox.getAttribute('aria-busy') !== 'true'",
                text,
            )
        )

    def _input(self) -> WebElement:
        root = self.root
        if root.get_dom_attribute("role") == "combobox":
            return root
        return root.find_element(By.CSS_SELECTOR, "[role=combobox]")

    def _active_option(self) -> str | None:
        return self.js(
            self._LISTBOX + " const id = input.getAttribute('aria-activedescendant');"
            " const o = id && document.getElementById(id);"
            " return o ? label(o) : null"
        )

    def _wait_chosen(self, text: str) -> None:
        self.waits.until(
            lambda _: not self.is_open() and self.selected() == text,
            f"{self} closed with '{text}' chosen",
        )


class MultiSelectDropdown(Element):
    """A checkbox per option: a toggle (aria-haspopup, else the first button) opens a panel of li,
    each with an input[type=checkbox]; the option's label is the li's text. The checked boxes are
    the value — opening and closing don't change it."""

    toggle_css = "[aria-haspopup], button"

    def select(self, *labels: str) -> Self:
        """Checks these options, leaving the others as they are."""
        return self._set_checked(True, labels)

    def deselect(self, *labels: str) -> Self:
        return self._set_checked(False, labels)

    def deselect_all(self) -> Self:
        return self.deselect(*self.selected())

    def selected(self) -> list[str]:
        return [text_of(li) for li, box in self._items() if box.is_selected()]

    def options(self) -> list[str]:
        return [text_of(li) for li, _ in self._items()]

    def visible_options(self) -> list[str]:
        """Options the panel's own search box leaves visible."""
        return [text_of(li) for li, _ in self._items() if li.is_displayed()]

    def filter(self, text: str) -> Self:
        """Types into the panel's search box."""
        self.open()
        search = self.root.find_element(By.CSS_SELECTOR, "input[type=search], input[type=text]")
        search.clear()
        search.send_keys(text)
        return self

    def open(self) -> Self:
        if not self.is_open():
            self._toggle().click()
            self.waits.until(lambda _: self.is_open(), f"{self} open")
        return self

    def close(self) -> Self:
        if self.is_open():
            self._toggle().click()
            self.waits.until(lambda _: not self.is_open(), f"{self} closed")
        return self

    def is_open(self) -> bool:
        return self._toggle().get_dom_attribute("aria-expanded") == "true"

    def _toggle(self) -> WebElement:
        return self.root.find_element(By.CSS_SELECTOR, self.toggle_css)

    def _items(self) -> list[tuple[WebElement, WebElement]]:
        items = []
        for li in self.root.find_elements(By.TAG_NAME, "li"):
            boxes = li.find_elements(By.CSS_SELECTOR, "input[type=checkbox]")
            if boxes:
                items.append((li, boxes[0]))
        return items

    def _set_checked(self, checked: bool, labels: tuple[str, ...]) -> Self:
        if not labels:
            return self
        self.open()
        for label in labels:
            match = [(li, box) for li, box in self._items() if text_of(li) == label]
            if not match:
                raise ValueError(f"No option '{label}' in {self}, options: {self.options()}")
            _, box = match[0]
            if box.is_selected() != checked:
                log.info("[%s] %s '%s'", self.label, "check" if checked else "uncheck", label)
                box.click()
                self.waits.until(
                    lambda _, b=box: b.is_selected() == checked,
                    f"{self} '{label}' {'checked' if checked else 'unchecked'}",
                )
        return self


class ReactSelectDropdown(Element):
    """react-select, declared on its control — the div whose generated class contains "-control".
    The control takes the click; the open menu renders div[role=option]; the chosen option is the
    control's "-singleValue". A searchable one lists options once text is typed."""

    _input_css = "input[role=combobox]"
    _option_xpath = "//div[@role='option'][normalize-space()={}]"

    def open(self) -> Self:
        # a dialog's fixed footer covers the bottom edge WebDriver scrolls to: the middle instead,
        # and while the dialog still moves, scroll and click again
        def opened(driver: WebDriver) -> bool:
            if not self.is_open():
                root = self.root
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", root)
                try:
                    root.click()
                except ElementClickInterceptedException:
                    return False
            return self.is_open()

        self.waits.until(opened, f"{self} open")
        return self

    def close(self) -> Self:
        if self.is_open():
            self._input().send_keys(Keys.ESCAPE)
            self.waits.until(lambda _: not self.is_open(), f"{self} closed")
        return self

    def is_open(self) -> bool:
        return self._input().get_dom_attribute("aria-expanded") == "true"

    def search(self, text: str) -> Self:
        self.open()
        self._input().send_keys(text)
        return self

    def select(self, text: str) -> Self:
        self.open()
        literal = f'"{text}"' if '"' not in text else f"'{text}'"
        offered = self.waits.until(
            lambda d: next(
                iter(d.find_elements(By.XPATH, self._option_xpath.format(literal))), None
            ),
            f"'{text}' offered by {self}",
        )
        log.info("[%s] select '%s'", self.label, text)
        offered.click()
        self.waits.until(lambda _: self.selected() == text, f"'{text}' chosen in {self}")
        return self

    def selected(self) -> str:
        chosen = self.root.find_elements(By.CSS_SELECTOR, "div[class*='-singleValue']")
        return text_of(chosen[0]) if chosen else ""

    def options(self) -> list[str]:
        return [
            text_of(o)
            for o in self.driver.find_elements(By.CSS_SELECTOR, "div[role=option]")
            if o.is_displayed()
        ]

    def is_enabled(self) -> bool:
        return self._input().is_enabled()

    def _input(self) -> WebElement:
        return self.root.find_element(By.CSS_SELECTOR, self._input_css)
