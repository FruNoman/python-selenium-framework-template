"""Every HTTP call as one block into the same log as the UI actions (logger "api", INFO) — the
same layout as the Java templates' `ApiLoggingFilter`: the request — method, URL, headers, form
params, pretty body — and the response — status, time, headers, pretty body — between lines of
`_`. A failed test's log then shows what was sent and answered, no debugger needed. One log
message per call, so parallel tests don't interleave. Credentials are masked: the credential
headers, and body / form fields named like a password, secret or token. A body over `MAX_BODY`
characters is cut (an HTML page, a big list).

Plugged into a `requests.Session` as a response hook (`log_calls(session)`): every call of that
session is logged, each redirect hop too.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qsl

import requests

log = logging.getLogger("api")

SEPARATOR = "_" * 100
MAX_BODY = 20_000
SECRET_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-csrf-token",
}
_SECRET_PART = re.compile(r"(?i)password|passwd|secret|token|api_?key")
# a name's words: camelCase, PascalCase, ACRONYMS, snake_case, kebab-case (CurrentPIN: Current PIN)
_WORDS = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")
# a JSON field with a string or number value: group 1 = up to the value, group 2 = the name
_JSON_FIELD = re.compile(r'("((?:[^"\\]|\\.)*)"\s*:\s*)("(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?)')


def is_secret_name(name: str) -> bool:
    """A field or form parameter whose value never prints: a password, a secret, a token, an API
    key — or a PIN (`PIN`, `pin`, `confirm_pin`, `CurrentPIN`, `NewPIN`; not `spinner`,
    `pinned`)."""
    return bool(_SECRET_PART.search(name)) or any(
        word.lower() == "pin" for word in _WORDS.findall(name)
    )


def log_calls(session: requests.Session) -> requests.Session:
    """Logs every call of the session (a response hook); returns the session."""
    session.hooks.setdefault("response", []).append(_hook)
    return session


def _hook(response: requests.Response, *_args: Any, **_kwargs: Any) -> requests.Response:
    log.info(entry(response))
    return response


def entry(response: requests.Response) -> str:
    """The block of one call."""
    request = response.request
    ms = int(response.elapsed.total_seconds() * 1000)
    parts = [
        "\n",
        SEPARATOR,
        f"\nREQUEST: {request.method} {request.url}\n",
        _headers(request.headers.items()),
    ]
    body = _text(request.body)
    content_type = _text(request.headers.get("Content-Type", ""))
    if body and "application/x-www-form-urlencoded" in content_type:
        parts.append(_form_params(parse_qsl(body, keep_blank_values=True)))
    elif body:
        parts.append(_body(_pretty(body)))
    parts += [
        f"RESPONSE: {response.status_code} ({ms} ms)\n",
        _headers(response.headers.items()),
        _body(_pretty(response.text)),
        SEPARATOR,
    ]
    return "".join(parts)


def _text(value: object) -> str:
    """A body or header value as text (requests keeps them as str or bytes; a stream: "")."""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value if isinstance(value, str) else ""


def _headers(headers: Iterable[tuple[str, str | bytes]]) -> str:
    return "".join(
        f"{name}: {_masked(name.lower() in SECRET_HEADERS, _text(value))}\n"
        for name, value in headers
    )


def _form_params(params: Iterable[tuple[str, str]]) -> str:
    return "".join(
        f"form: {name}={_masked(is_secret_name(name), value)}\n" for name, value in params
    )


def _masked(secret: bool, value: str) -> str:
    return "***" if secret else value


def _pretty(text: str) -> str:
    """JSON indented (4 spaces, as REST Assured's prettifier); anything else as it came."""
    stripped = text.strip()
    if stripped[:1] in ("{", "["):
        try:
            return json.dumps(json.loads(stripped), indent=4, ensure_ascii=False)
        except ValueError:
            return text
    return text


def _body(body: str) -> str:
    """The body, its secret fields masked and cut at MAX_BODY; "" when there is none."""
    if not body:
        return ""
    safe = _JSON_FIELD.sub(
        lambda m: f'{m.group(1)}"***"' if is_secret_name(m.group(2)) else m.group(0), body
    )
    if len(safe) > MAX_BODY:
        safe = f"{safe[:MAX_BODY]}\n… ({len(safe) - MAX_BODY} more characters)"
    return safe + "\n"
