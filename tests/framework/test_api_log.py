"""The API log's layout — the Java templates' `ApiLoggingFilter`: one block per call between `_`
lines, REQUEST / RESPONSE, headers, `form:` lines, pretty JSON, secrets masked. No network: the
request and the response are built here."""

from __future__ import annotations

import datetime as dt

import requests
from pytest_check import check

from autotests.api.log import SEPARATOR, entry


def _exchange(request: requests.Request, status: int, body: str, **headers: str) -> str:
    response = requests.Response()
    response.request = request.prepare()
    response.status_code = status
    response._content = body.encode()
    response.headers.update(headers)
    response.elapsed = dt.timedelta(milliseconds=42)
    return entry(response)


def test_a_json_call_is_one_block_with_secrets_masked() -> None:
    block = _exchange(
        requests.Request(
            "POST",
            "https://app.example/api/orders",
            headers={"Authorization": "Bearer abc", "Accept": "application/json"},
            json={"sku": "A-1", "password": "s3cret"},
        ),
        201,
        '{"id": 7, "token": "xyz"}',
        **{"Content-Type": "application/json", "Set-Cookie": "SESSION=1"},
    )
    lines = block.splitlines()

    with check:
        assert lines[1] == SEPARATOR, "between ____ lines"
        assert lines[-1] == SEPARATOR, "between ____ lines"
    with check:
        assert "REQUEST: POST https://app.example/api/orders" in lines
    with check:
        assert "Authorization: ***" in lines
        assert "Accept: application/json" in lines
    with check:
        assert '    "password": "***"' in lines, "pretty, masked"
        assert '    "sku": "A-1",' in lines, "pretty, masked"
    with check:
        assert "RESPONSE: 201 (42 ms)" in lines
    with check:
        assert "Set-Cookie: ***" in lines
        assert '    "token": "***"' in lines


def test_a_form_post_is_logged_as_form_lines() -> None:
    block = _exchange(
        requests.Request(
            "POST",
            "https://app.example/login",
            data={"email": "a@b.c", "password": "pw", "_token": "t"},
        ),
        302,
        "",
        Location="/home",
    )
    lines = block.splitlines()

    with check:
        assert "form: email=a@b.c" in lines
    with check:
        assert "form: password=***" in lines
        assert "form: _token=***" in lines
    with check:
        assert "RESPONSE: 302 (42 ms)" in lines
        assert "Location: /home" in lines


def test_pins_and_the_csrf_header_are_masked_not_words_containing_pin() -> None:
    block = _exchange(
        requests.Request(
            "POST",
            "https://app.example/api/pin",
            headers={"X-CSRF-TOKEN": "csrf-value"},
            json={
                "PIN": "1111",
                "pin": 2222,
                "confirm_pin": "3333",
                "CurrentPIN": "4444",
                "NewPIN": "5555",
                "spinner": "on",
                "pinned": "yes",
            },
        ),
        200,
        "{}",
    )

    with check:
        assert "X-CSRF-TOKEN: ***" in block.splitlines(), "the CSRF header"
    with check:
        assert not any(pin in block for pin in ("1111", "2222", "3333", "4444", "5555")), "PINs"
    with check:
        assert '"spinner": "on"' in block, "a word containing pin stays"
        assert '"pinned": "yes"' in block, "a word containing pin stays"
