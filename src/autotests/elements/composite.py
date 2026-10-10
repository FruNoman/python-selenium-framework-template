"""Tables, dialogs, toasts, tabs, menus, pagers."""

from __future__ import annotations

import re
from typing import Self

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from autotests.elements.core import Element, has_class, is_aria_disabled, log, text_of
from autotests.elements.dropdown import SelectDropdown

_CELLS = (By.XPATH, "./th|./td")


class Table(Element):
    """A <table> read by column header: `table.cell(table.row("Name", "Ada L."), "Role")`.
    Headers = texts of the last thead row; a data row = a displayed tbody tr that isn't one cell
    spanning the table ("No results"). `sort_by` clicks the header's control and waits until the
    table shows something else; `sort_state` is its aria-sort."""

    def headers(self) -> list[str]:
        return [text_of(h) for h in self._heads()]

    def row_count(self) -> int:
        return len(self.rows())

    def is_empty(self) -> bool:
        return self.row_count() == 0

    def rows(self) -> list[WebElement]:
        return [
            tr
            for tr in self.root.find_elements(By.CSS_SELECTOR, "tbody > tr")
            if self._is_data_row(tr)
        ]

    def row(self, column: str, value: str) -> WebElement:
        """The first row whose `column` reads exactly `value`."""
        row = self.find_row(column, value)
        if row is None:
            raise ValueError(
                f"No row with {column} = '{value}' in {self}, column has: {self.column(column)}"
            )
        return row

    def find_row(self, column: str, value: str) -> WebElement | None:
        index = self._index(column)
        return next((r for r in self.rows() if self._cell_text(r, index) == value), None)

    def cell(self, row: WebElement, column: str) -> WebElement:
        return row.find_elements(*_CELLS)[self._index(column)]

    def cell_text(self, row: WebElement, column: str) -> str:
        return self._cell_text(row, self._index(column))

    def values(self, row: WebElement) -> dict[str, str]:
        """Header → cell text of one row."""
        return dict(
            zip(self.headers(), (text_of(c) for c in row.find_elements(*_CELLS)), strict=False)
        )

    def rows_values(self) -> list[dict[str, str]]:
        headers = self.headers()
        return [
            dict(zip(headers, (text_of(c) for c in r.find_elements(*_CELLS)), strict=False))
            for r in self.rows()
        ]

    def column(self, column: str) -> list[str]:
        index = self._index(column)
        return [self._cell_text(r, index) for r in self.rows()]

    def sort_by(self, column: str) -> Self:
        """Clicks the column's header control; returns once the table has changed."""
        head = self._heads()[self._index(column)]
        controls = head.find_elements(By.CSS_SELECTOR, "a, button, [role=button]")
        control = controls[0] if controls else head
        log.info("[%s] sort by %s", self.label, column)
        self.waits.for_change(
            lambda: self.sort_state(column) + "|" + self.text(),
            control.click,
            f"{self} sorted by {column}",
        )
        return self

    def sort_state(self, column: str) -> str:
        """aria-sort: ascending, descending, none (or other when absent)."""
        return self._heads()[self._index(column)].get_dom_attribute("aria-sort") or "none"

    def _heads(self) -> list[WebElement]:
        rows = self.root.find_elements(By.CSS_SELECTOR, "thead tr")
        return rows[-1].find_elements(*_CELLS) if rows else []

    @staticmethod
    def _is_data_row(tr: WebElement) -> bool:
        # not a "No results" placeholder spanning the table (a colspan that isn't a plain number,
        # "100%", spans it too) and not hidden by a client-side filter
        cells = tr.find_elements(*_CELLS)
        span = cells[0].get_dom_attribute("colspan") if len(cells) == 1 else None
        placeholder = span is not None and (not span.strip().isdigit() or int(span) > 1)
        return not placeholder and tr.is_displayed()

    @staticmethod
    def _cell_text(row: WebElement, index: int) -> str:
        cells = row.find_elements(*_CELLS)
        return text_of(cells[index]) if index < len(cells) else ""

    def _index(self, column: str) -> int:
        headers = self.headers()
        if column not in headers:
            raise ValueError(f"No column '{column}' in {self}, headers: {headers}")
        return headers.index(column)


class Modal(Element):
    """A dialog — role=dialog|alertdialog or <dialog> — declared on it or on the backdrop. Buttons
    by meaning: confirm = [data-action=confirm], else the primary/danger one, else the last; cancel
    = [data-action=cancel], else the one named Cancel/Close, else the first. Title and message via
    aria-labelledby / aria-describedby, else the first heading / paragraph."""

    _DIALOG = "[role=dialog], [role=alertdialog], dialog"
    _CANCEL = re.compile(r"(?i)cancel|close|×")

    def is_open(self) -> bool:
        return self.is_visible() and self._dialog().is_displayed()

    def wait_open(self) -> Self:
        self.waits.until(lambda _: self.is_open(), f"{self} open")
        return self

    def wait_closed(self) -> Self:
        self.waits.until(lambda _: not self.is_open(), f"{self} closed")
        return self

    def title(self) -> str:
        return self._referenced("aria-labelledby") or self._first("h1, h2, h3, h4, h5, h6")

    def message(self) -> str:
        return self._referenced("aria-describedby") or self._first("p")

    def confirm(self) -> None:
        """Clicks the confirming button. No wait: what follows is the caller's (a new document,
        the dialog closing, or staying open with an error)."""
        buttons = self._buttons()
        button = (
            self._by_action(buttons, "confirm")
            or next(
                (
                    b
                    for b in buttons
                    if any(
                        has_class(b, c) for c in ("btn-primary", "btn-danger", "primary", "danger")
                    )
                ),
                None,
            )
            or buttons[-1]
        )
        log.info("[%s] confirm", self.label)
        button.click()

    def cancel(self) -> None:
        """Clicks the cancelling button and waits until the dialog is gone."""
        buttons = self._buttons()
        button = (
            self._by_action(buttons, "cancel")
            or next((b for b in buttons if self._CANCEL.fullmatch(self._name(b))), None)
            or buttons[0]
        )
        log.info("[%s] cancel", self.label)
        button.click()
        self.wait_closed()

    def click_button(self, text: str) -> None:
        for button in self._buttons():
            if self._name(button) == text:
                log.info("[%s] click '%s'", self.label, text)
                button.click()
                return
        raise ValueError(f"No button '{text}' in {self}, buttons: {self.buttons()}")

    def buttons(self) -> list[str]:
        return [self._name(b) for b in self._buttons()]

    def _dialog(self) -> WebElement:
        root = self.root
        if root.tag_name == "dialog" or root.get_dom_attribute("role") in ("dialog", "alertdialog"):
            return root
        inner = root.find_elements(By.CSS_SELECTOR, self._DIALOG)
        return inner[0] if inner else root

    def _buttons(self) -> list[WebElement]:
        return self._dialog().find_elements(By.CSS_SELECTOR, "button, [role=button]")

    def _referenced(self, attribute: str) -> str:
        element_id = self._dialog().get_dom_attribute(attribute)
        found = self.driver.find_elements(By.ID, element_id) if element_id else []
        return text_of(found[0]) if found else ""

    def _first(self, css: str) -> str:
        found = self._dialog().find_elements(By.CSS_SELECTOR, css)
        return text_of(found[0]) if found else ""

    @staticmethod
    def _by_action(buttons: list[WebElement], action: str) -> WebElement | None:
        return next((b for b in buttons if b.get_dom_attribute("data-action") == action), None)

    @staticmethod
    def _name(button: WebElement) -> str:
        label = button.get_dom_attribute("aria-label")
        return label.strip() if label is not None else text_of(button)


class Toasts(Element):
    """Where notifications appear — declared on their container, or on body to catch any. A toast
    is a visible role=status / role=alert element (the root counts). They come and go on their own
    timers: wait for the one you expect, then for it to go if that matters."""

    def texts(self) -> list[str]:
        root = self.root
        candidates = root.find_elements(By.CSS_SELECTOR, "[role=status], [role=alert]")
        if root.get_dom_attribute("role") in ("status", "alert"):
            candidates.insert(0, root)
        texts = []
        for candidate in candidates:
            try:
                if candidate.is_displayed() and text_of(candidate):
                    texts.append(text_of(candidate))
            except StaleElementReferenceException:
                pass  # removed by its own timer meanwhile
        return texts

    def wait_for(self, text: str) -> str:
        """Waits for a toast containing `text`; returns its full text."""
        return self.waits.until(
            lambda _: next((t for t in self.texts() if text in t), None),
            f"a toast with '{text}' in {self}",
        )

    def wait_gone(self, text: str) -> Self:
        self.waits.until(
            lambda _: all(text not in t for t in self.texts()), f"no toast with '{text}' in {self}"
        )
        return self


class Tabs(Element):
    """WAI-ARIA tabs, declared on the element holding the tablist: role=tab items, each
    aria-controls its role=tabpanel. `select` returns once the tab is selected and its panel shown
    and loaded (not aria-busy; past idle/loading when it carries data-state)."""

    def select(self, name: str) -> Self:
        tab = self._tab(name)
        log.info("[%s] select '%s'", self.label, name)
        tab.click()
        self.waits.until(
            lambda _: self._selected(tab) and self._loaded(self._panel(tab)),
            f"{self} '{name}' selected and loaded",
        )
        return self

    def selected(self) -> str:
        tab = self._selected_tab()
        return text_of(tab) if tab else ""

    def tabs(self) -> list[str]:
        return [text_of(t) for t in self._tabs()]

    def panel_text(self) -> str:
        tab = self._selected_tab()
        return text_of(self._panel(tab)) if tab else ""

    def _tabs(self) -> list[WebElement]:
        return self.root.find_elements(By.CSS_SELECTOR, "[role=tab]")

    def _tab(self, name: str) -> WebElement:
        for tab in self._tabs():
            if text_of(tab) == name:
                return tab
        raise ValueError(f"No tab '{name}' in {self}, tabs: {self.tabs()}")

    def _selected_tab(self) -> WebElement | None:
        return next((t for t in self._tabs() if self._selected(t)), None)

    def _panel(self, tab: WebElement) -> WebElement:
        return self.driver.find_element(By.ID, tab.get_dom_attribute("aria-controls"))

    @staticmethod
    def _selected(tab: WebElement) -> bool:
        return tab.get_dom_attribute("aria-selected") == "true"

    @staticmethod
    def _loaded(panel: WebElement) -> bool:
        return (
            panel.is_displayed()
            and panel.get_dom_attribute("aria-busy") != "true"
            and panel.get_dom_attribute("data-state") not in ("idle", "loading")
        )


class Menu(Element):
    """A menu button, declared on the element holding the trigger (a toolbar, a table cell): the
    trigger has aria-haspopup; the role=menu is the one its aria-controls names (a portal) or the
    one inside. Items role=menuitem*; disabled = aria-disabled=true."""

    def open(self) -> Self:
        if not self.is_open():
            self._trigger().click()
            self.waits.until(lambda _: self.is_open(), f"{self} open")
        return self

    def choose(self, item: str) -> None:
        """Opens the menu, clicks the item, waits until the menu is closed — or gone (Delete may
        remove the row it was in)."""
        self.open()
        element = self._item(item)
        if is_aria_disabled(element):
            raise ValueError(f"Item '{item}' of {self} is disabled")
        log.info("[%s] choose '%s'", self.label, item)
        element.click()
        self.waits.until(lambda _: not self._open_or_gone(), f"{self} closed after '{item}'")

    def is_open(self) -> bool:
        menu = self._menu()
        return menu is not None and menu.is_displayed()

    def is_item_enabled(self, item: str) -> bool:
        return not is_aria_disabled(self._item(item))

    def items(self) -> list[str]:
        return [text_of(i) for i in self._items()]

    def _trigger(self) -> WebElement:
        root = self.root
        if root.get_dom_attribute("aria-haspopup") is not None:
            return root
        return root.find_element(By.CSS_SELECTOR, "[aria-haspopup]")

    def _menu(self) -> WebElement | None:
        controls = self._trigger().get_dom_attribute("aria-controls")
        if controls:
            portal = self.driver.find_elements(By.ID, controls)
            if portal:
                return portal[0]
        inner = self.root.find_elements(By.CSS_SELECTOR, "[role=menu]")
        return inner[0] if inner else None

    def _items(self) -> list[WebElement]:
        menu = self._menu()
        return menu.find_elements(By.CSS_SELECTOR, "[role^=menuitem]") if menu else []

    def _item(self, name: str) -> WebElement:
        for item in self._items():
            if text_of(item) == name:
                return item
        raise ValueError(f"No item '{name}' in {self}, items: {self.items()}")

    def _open_or_gone(self) -> bool:
        try:
            return self.is_open()
        except StaleElementReferenceException:
            return False


class Pagination(Element):
    """A pager: previous/next and page-number controls — buttons (re-render) or links (a new
    document), both waited for until the pager shows something else. Found by rel, aria-label or
    text: prev = rel=prev / "Prev…" / ‹ «, next = rel=next / "Next…" / › », page n = "n" or a label
    ending in "page n". Disabled = disabled, aria-disabled=true or a "disabled" class on it or its
    li."""

    _PREV = re.compile(r"(?i)^(prev|previous|‹|«).*")
    _NEXT = re.compile(r"(?i)^(next|›|»).*")

    def next(self) -> Self:
        return self._go(self._control("next", self._NEXT), "next page")

    def prev(self) -> Self:
        return self._go(self._control("prev", self._PREV), "previous page")

    def go_to(self, page: int) -> Self:
        label = re.compile(rf"(?i).*page\s*{page}$")
        control = next(
            (
                c
                for c in self._controls()
                if text_of(c) == str(page) or label.match(c.get_dom_attribute("aria-label") or "")
            ),
            None,
        )
        return self._go(control, f"page {page}")

    def has_next(self) -> bool:
        control = self._control("next", self._NEXT)
        return control is not None and not self._disabled(control)

    def has_prev(self) -> bool:
        control = self._control("prev", self._PREV)
        return control is not None and not self._disabled(control)

    def set_page_size(self, size: int) -> Self:
        """Picks the page size in the pager's own <select>; returns after the re-render."""
        select = self.part(By.TAG_NAME, "select", "page size", SelectDropdown)
        self.waits.for_change(
            self._snapshot, lambda: select.select(str(size)), f"{self} after page size {size}"
        )
        return self

    def info(self) -> str:
        """The pager's own text without its controls — "Page 2 of 3 (23 rows)"."""
        return self.js(
            "const c = arguments[0].cloneNode(true);"
            " c.querySelectorAll('a, button, select, label').forEach(e => e.remove());"
            " return c.textContent.replace(/\\s+/g, ' ').trim()"
        )

    def _go(self, control: WebElement | None, what: str) -> Self:
        if control is None or self._disabled(control):
            raise ValueError(f"{self} has no enabled '{what}' control, shows: {self.info()}")
        log.info("[%s] %s", self.label, what)
        self.waits.for_change(self._snapshot, control.click, f"{self} after '{what}'")
        return self

    def _controls(self) -> list[WebElement]:
        return self.root.find_elements(By.CSS_SELECTOR, "a, button")

    def _control(self, rel: str, name: re.Pattern[str]) -> WebElement | None:
        return next(
            (
                c
                for c in self._controls()
                if c.get_dom_attribute("rel") == rel or name.match(self._name(c))
            ),
            None,
        )

    @staticmethod
    def _name(control: WebElement) -> str:
        label = control.get_dom_attribute("aria-label")
        return label.strip() if label is not None else text_of(control)

    @staticmethod
    def _disabled(control: WebElement) -> bool:
        return (
            not control.is_enabled()
            or is_aria_disabled(control)
            or has_class(control, "disabled")
            or bool(
                control.find_elements(
                    By.XPATH, "parent::li[contains(concat(' ', @class, ' '), ' disabled ')]"
                )
            )
        )

    def _snapshot(self) -> str:
        return self.root.get_property("innerHTML") or ""
