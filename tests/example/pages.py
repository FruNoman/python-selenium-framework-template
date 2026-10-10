"""Example pages — Selenium's own test form (base.url in resources/env/dev.yml): how a page is
written, and what the example tests and CI run until the project has its own pages. Template repo
only: onboarding deletes tests/example/ and resources/data/web-form-data.json right after cloning.

Page conventions shown: the URL path for open(); private element attributes typed with the
standard elements; the test talks to the page, never to its elements — a fluent method per user
action, a read per value; an action that loads a new document waits for it and returns the next
page. The app's pages go to src/autotests/pages/<area>/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Self

from selenium.webdriver.common.by import By

from autotests.elements import (
    Button,
    CheckBox,
    Element,
    FileUpload,
    Input,
    RadioGroup,
    SelectDropdown,
)
from autotests.pages.base_page import BasePage


class SubmittedPage(BasePage):
    """Where WebFormPage.submit() lands — "Form submitted" with its message."""

    path = "submitted-form.html"
    _message = Element(By.ID, "message")

    def message(self) -> str:
        return self._message.text()


class WebFormPage(BasePage):
    path = "web-form.html"

    _text = Input(By.NAME, "my-text")
    _textarea = Input(By.NAME, "my-textarea")
    _disabled_input = Input(By.NAME, "my-disabled")
    _readonly_input = Input(By.NAME, "my-readonly")
    _options = SelectDropdown(By.NAME, "my-select")
    _file = FileUpload(By.NAME, "my-file")
    _default_checkbox = CheckBox(By.ID, "my-check-2")
    # no wrapper around the two radios: the form holds them, and no other radios
    _radios = RadioGroup(By.TAG_NAME, "form")
    _submit = Button(By.CSS_SELECTOR, "button[type=submit]")

    def type_text(self, value: str) -> Self:
        self._text.clear_and_type(value)
        return self

    def type_textarea(self, value: str) -> Self:
        self._textarea.clear_and_type(value)
        return self

    def choose_option(self, text: str) -> Self:
        self._options.select(text)
        return self

    def set_default_checked(self, checked: bool) -> Self:
        self._default_checkbox.set_checked(checked)
        return self

    def choose_radio(self, label: str) -> Self:
        self._radios.select(label)
        return self

    def upload(self, file: Path) -> Self:
        self._file.upload(file)
        return self

    def submit(self) -> SubmittedPage:
        self.waits.for_new_document(self._submit.click, "the submitted form")
        return SubmittedPage(self.browser).wait_loaded()

    def text(self) -> str:
        return self._text.value()

    def textarea(self) -> str:
        return self._textarea.value()

    def is_disabled_input_enabled(self) -> bool:
        return self._disabled_input.root.is_enabled()

    def is_readonly_input_read_only(self) -> bool:
        return self._readonly_input.is_read_only()

    def option(self) -> str:
        return self._options.selected()

    def option_value(self) -> str:
        return self._options.selected_value()

    def is_default_checked(self) -> bool:
        return self._default_checkbox.is_checked()

    def radio(self) -> str:
        return self._radios.selected()

    def radio_options(self) -> list[str]:
        return self._radios.options()

    def uploaded_files(self) -> list[str]:
        return self._file.file_names()
