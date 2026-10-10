"""The example's fixtures: its entry page and its data. A project's own fixtures follow the same
shape in tests/conftest.py (and tests/<area>/conftest.py)."""

from __future__ import annotations

import pytest

from autotests.data import TestData, data_fixture
from autotests.pages.base_page import Browser
from tests.example.pages import WebFormPage


class WebFormData(TestData):
    """The example's input and expected values (resources/data/web-form-data.json)."""

    text: str
    textarea: str
    option: str
    option_value: str
    missing_option: str
    radio: str
    radios: list[str]
    file: str
    file_name: str
    message: str


web_form_data = data_fixture(WebFormData)


@pytest.fixture
def web_form_page(browser: Browser) -> WebFormPage:
    """The tests' entry page, open."""
    return WebFormPage(browser).open()
