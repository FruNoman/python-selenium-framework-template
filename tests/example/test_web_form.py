"""Example tests on Selenium's test form — the standard elements in use, data from JSON as fixtures
(`web_form_data` = "default", parametrized indirectly for another variant), soft checks.
Template repo only — removed with tests/example/ when a project is created."""

from __future__ import annotations

import pytest
from pytest_check import check

from autotests.config.settings import ROOT
from tests.example.conftest import WebFormData
from tests.example.pages import WebFormPage


def test_inputs(web_form_page: WebFormPage, web_form_data: WebFormData) -> None:
    web_form_page.type_text(web_form_data.text).type_textarea(web_form_data.textarea)

    with check:
        assert web_form_page.text() == web_form_data.text, "typed text"
    with check:
        assert web_form_page.textarea() == web_form_data.textarea, "textarea"
    with check:
        assert not web_form_page.is_disabled_input_enabled(), "disabled input"
    with check:
        assert web_form_page.is_readonly_input_read_only(), "read-only input"


@pytest.mark.parametrize("web_form_data", ["second-option"], indirect=True)
def test_choices(web_form_page: WebFormPage, web_form_data: WebFormData) -> None:
    (
        web_form_page.choose_option(web_form_data.option)
        .set_default_checked(True)
        .choose_radio(web_form_data.radio)
        .upload(ROOT / "resources" / web_form_data.file)
    )

    with check:
        assert web_form_page.option() == web_form_data.option, "by visible text"
    with check:
        assert web_form_page.option_value() == web_form_data.option_value, "its value"
    with check:
        assert web_form_page.is_default_checked(), "checkbox"
    with check:
        assert web_form_page.radio() == web_form_data.radio, "radio by its label"
    with check:
        assert web_form_page.radio_options() == web_form_data.radios
    with check:
        assert web_form_page.uploaded_files() == [web_form_data.file_name]


def test_an_option_the_select_doesnt_have_is_refused(
    web_form_page: WebFormPage, web_form_data: WebFormData
) -> None:
    with pytest.raises(ValueError, match=web_form_data.missing_option):
        web_form_page.choose_option(web_form_data.missing_option)


def test_submit(web_form_page: WebFormPage, web_form_data: WebFormData) -> None:
    submitted_page = web_form_page.type_text(web_form_data.text).submit()

    assert submitted_page.message() == web_form_data.message, "the confirmation page's message"
