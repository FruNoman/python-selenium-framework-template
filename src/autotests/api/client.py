"""HTTP to the app: `ApiClient` for its API (JSON, auth per user, logged), `WebClient` for plain
requests to the web app (redirects not followed — a 302 is an answer to check).

The app's clients live in `api/<area>/` (`OrdersApi(api_client)`), their DTOs (pydantic models) in
`api/<area>/dto.py`; a client method takes the request DTO and returns the parsed response —
never a dict built field by field.
"""

from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

import requests
from pydantic import BaseModel

from autotests.auth.users import User

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)

_SECRET_KEYS = ("password", "token", "secret", "authorization", "cookie")


def _masked(body: Any) -> Any:
    if isinstance(body, dict):
        return {
            k: "***" if any(s in k.lower() for s in _SECRET_KEYS) else _masked(v)
            for k, v in body.items()
        }
    if isinstance(body, list):
        return [_masked(v) for v in body]
    return body


class ApiResponse:
    def __init__(self, response: requests.Response) -> None:
        self.raw = response

    @property
    def status(self) -> int:
        return self.raw.status_code

    def expect_status(self, *expected: int) -> ApiResponse:
        if self.raw.status_code not in expected:
            raise AssertionError(
                f"{self.raw.request.method} {self.raw.url} → {self.raw.status_code}, expected "
                f"{expected}: {self.raw.text[:500]}"
            )
        return self

    def json(self) -> Any:
        return self.raw.json()

    def as_model(self, model: type[M]) -> M:
        return model.model_validate(self.raw.json())

    def text(self) -> str:
        return self.raw.text

    @property
    def headers(self) -> Any:
        return self.raw.headers


class ApiClient:
    """The app's API. `as_user(user)` sends the user's credential — ONBOARD: how the app
    authenticates (a bearer token from the IdP, a session cookie, an API key); tokens cached per
    user until shortly before they expire, never logged."""

    def __init__(self, base_url: str, timeout: float = 30) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout

    def as_user(self, user: User | None = None) -> _Session:
        session = requests.Session()
        session.headers["Accept"] = "application/json"
        if user is not None:
            self.authenticate(session, user)
        return _Session(self, session)

    def authenticate(self, session: requests.Session, user: User) -> None:
        """ONBOARD: put the user's credential on the session (header or cookie)."""
        raise NotImplementedError("ApiClient.authenticate: onboard the app's API auth first")


class _Session:
    def __init__(self, client: ApiClient, session: requests.Session) -> None:
        self.client, self.session = client, session

    def request(
        self,
        method: str,
        path: str,
        body: BaseModel | dict | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ApiResponse:
        url = path if path.startswith("http") else self.client.base_url + path.lstrip("/")
        payload = (
            body.model_dump(mode="json", by_alias=True, exclude_none=True)
            if isinstance(body, BaseModel)
            else body
        )
        response = self.session.request(
            method, url, json=payload, params=params, timeout=self.client.timeout, **kwargs
        )
        log.info(
            "%s %s%s → %s",
            method,
            url,
            f" {json.dumps(_masked(payload))[:300]}" if payload is not None else "",
            response.status_code,
        )
        return ApiResponse(response)

    def get(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, body: BaseModel | dict | None = None, **kwargs: Any) -> ApiResponse:
        return self.request("POST", path, body, **kwargs)

    def put(self, path: str, body: BaseModel | dict | None = None, **kwargs: Any) -> ApiResponse:
        return self.request("PUT", path, body, **kwargs)

    def patch(self, path: str, body: BaseModel | dict | None = None, **kwargs: Any) -> ApiResponse:
        return self.request("PATCH", path, body, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("DELETE", path, **kwargs)


class WebClient:
    """Plain HTTP to the web app (a login form, a redirect check) — redirects are answers here."""

    def __init__(self, base_url: str, timeout: float = 30) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.session = requests.Session()

    def get(self, path: str, **kwargs: Any) -> ApiResponse:
        url = path if path.startswith("http") else self.base_url + path.lstrip("/")
        response = self.session.get(url, allow_redirects=False, timeout=self.timeout, **kwargs)
        log.info("GET %s → %s", url, response.status_code)
        return ApiResponse(response)

    def post_form(self, path: str, form: dict[str, str], **kwargs: Any) -> ApiResponse:
        url = path if path.startswith("http") else self.base_url + path.lstrip("/")
        response = self.session.post(
            url, data=form, allow_redirects=False, timeout=self.timeout, **kwargs
        )
        log.info("POST %s → %s", url, response.status_code)
        return ApiResponse(response)
