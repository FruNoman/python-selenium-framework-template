"""Who a test runs as. The logins are test data — resources/data/user-data.json, a row per user
(lower case: {"user": {"username": …, "password": …}}), another environment's in
resources/data/<env>/user-data.json — never env vars, CI secrets or YAML; passwords never print.

The default user is the least privileged one: a test needing more says `@pytest.mark.as_user(
User.ADMIN)` — an admin sees everything, so a permission check missing in the app would pass
unnoticed under one.
"""

from __future__ import annotations

from enum import Enum

from pydantic import SecretStr

from autotests.data.models import TestData


class User(Enum):
    # ONBOARD: the app's roles — the least privileged first (the default)
    USER = "user"
    ADMIN = "admin"


class Credentials(TestData):
    username: str
    password: SecretStr
    display_name: str | None = None
