"""Data and texts reach a test as fixtures named after them — never `loader.load(...)` in a body.

    # tests/conftest.py
    web_form_data = data_fixture(WebFormData)          # fixture "web_form_data"
    login_texts = texts_fixture("login")               # the app's texts of one area

    def test_submit(web_form_page, web_form_data): ...                    # variant "default"

    @pytest.mark.parametrize("web_form_data", ["second-option"], indirect=True)
    def test_choices(web_form_page, web_form_data): ...                   # another variant

    @pytest.mark.parametrize("invalid_field_data", variant_names(InvalidFieldData), indirect=True)
    def test_rejected(form_page, invalid_field_data): ...                 # a data table: a row each

The test's id carries the variant's name ("test_rejected[price-negative]") — short and stable.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from autotests.data.loader import TestDataLoader


def data_fixture(model: type[BaseModel]) -> Callable[..., Any]:
    """A function-scoped fixture loading `model`: "default", or the variant parametrized
    indirectly. Fresh placeholders per test."""

    @pytest.fixture
    def fixture(request: pytest.FixtureRequest, test_data_loader: TestDataLoader) -> BaseModel:
        return test_data_loader.load(model, getattr(request, "param", "default"))

    fixture.__doc__ = f"{model.__name__} from {model.__name__} test data (variant: default)"
    return fixture


def texts_fixture(area: str) -> Callable[..., Any]:
    """The app's fixed texts of one area of ui-texts.json — `<area>_texts`. Loaded once per run."""

    @pytest.fixture(scope="session")
    def fixture(ui_texts: dict[str, Any]) -> Any:
        if area not in ui_texts:
            raise KeyError(f"No area '{area}' in ui-texts.json: {list(ui_texts)}")
        return _Texts(area, ui_texts[area])

    return fixture


class _Texts:
    """An area's texts as attributes (`login_texts.wrong_credentials`); nested areas nest."""

    def __init__(self, area: str, values: dict[str, Any]) -> None:
        self._area = area
        for key, value in values.items():
            setattr(
                self,
                _snake(key),
                _Texts(f"{area}.{key}", value) if isinstance(value, dict) else value,
            )

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"No text '{name}' in ui-texts.json area '{self._area}'")

    def __repr__(self) -> str:
        return f"Texts[{self._area}]"


def _snake(name: str) -> str:
    out = []
    for char in name:
        if char.isupper():
            out.append("_" + char.lower())
        else:
            out.append(char)
    return "".join(out).replace("-", "_")
