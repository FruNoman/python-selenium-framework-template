"""The framework's layers without a browser: settings, test data, cleanup, the API client."""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from pydantic import SecretStr
from pytest_check import check

from autotests.api.client import ApiClient
from autotests.config.settings import load_settings
from autotests.data.loader import TestDataLoader
from autotests.data.models import TestData
from autotests.data.placeholders import process
from autotests.support import shared_state

# --- settings


def test_settings_layers_env_vars_and_options() -> None:
    from_env = load_settings(environ={"BASE_URL": "https://stage.example/", "HEADLESS": "false"})
    from_cli = load_settings({"browser.name": "firefox", "runner": "grid"}, environ={})

    with check:
        assert from_env.base.url == "https://stage.example/", "an env var overrides the env file"
    with check:
        assert from_env.browser.headless is False, "and a nested setting"
    with check:
        assert (from_cli.browser.name, from_cli.runner) == ("firefox", "grid"), "CLI options"
    with check:
        assert load_settings(environ={"CI": "true"}).waits.timeout == 20, "the CI layer"


def test_an_unknown_environment_fails_fast() -> None:
    with pytest.raises(FileNotFoundError, match="No environment 'nowhere'"):
        load_settings({"env": "nowhere"}, environ={})


# --- test data


class SampleData(TestData):
    name: str
    born: dt.date
    password: SecretStr | None = None


def test_placeholders_give_fresh_values() -> None:
    values = json.loads(
        process(
            json.dumps(
                [
                    "{{uniqueTimestamp}}",
                    "{{uniqueTimestamp}}",
                    "{{random:6}}",
                    "{{text:12}}",
                    "{{inDays:-1}}",
                    "{{firstname}}",
                ]
            )
        )
    )

    with check:
        assert values[0] != values[1], "uniqueTimestamp never twice"
    with check:
        assert len(values[2]) == 6 and values[2][0] != "0", "random:N — N digits, no leading 0"
    with check:
        assert len(values[3]) == 12, "text:N"
    with check:
        assert values[4] == (dt.date.today() - dt.timedelta(days=1)).isoformat(), "ISO by default"
    with check:
        assert process("{{today:%m/%d/%Y}}") == dt.date.today().strftime("%m/%d/%Y"), "strftime"


def test_variants_env_overrides_and_masked_secrets(tmp_path: Path) -> None:
    env = load_settings(environ={}).env  # the project's default env — "dev" until it's renamed
    (tmp_path / "data" / env).mkdir(parents=True)
    (tmp_path / "data" / "sample-data.json").write_text(
        json.dumps({"default": {"name": "{{firstname}}", "born": "{{yesterday}}"}})
    )
    # an environment's file replaces the shared one whole — its own variants, all of them
    (tmp_path / "data" / env / "sample-data.json").write_text(
        json.dumps(
            {
                "default": {"name": "Dev's own", "born": "2000-01-01"},
                "admin": {"name": "Ada", "born": "1815-12-10", "password": "s3cret"},
            }
        )
    )
    loader = TestDataLoader(load_settings({"data.dir": str(tmp_path / "data")}, environ={}))

    default = loader.load(SampleData)
    admin = loader.load(SampleData, "admin")

    with check:
        assert default.name == "Dev's own", "data/<env>/ wins"
    with check:
        assert admin.born == dt.date(1815, 12, 10), "a date parsed"
    with check:
        assert "s3cret" not in repr(admin) and "s3cret" not in str(admin.password), "secret hidden"
    with check:
        assert loader.variant_names(SampleData) == ["default", "admin"], "the env file's variants"


# --- API


class _Echo(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def echo_server():
    server = HTTPServer(("127.0.0.1", 0), _Echo)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()


class Login(TestData):
    username: str
    password: str


def test_api_client_sends_dtos_and_masks_secrets(
    echo_server: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    response = (
        ApiClient(echo_server)
        .as_user()
        .post("login", Login(username="ada", password="s3cret"))
        .expect_status(201)
    )

    with check:
        assert response.as_model(Login).username == "ada", "the DTO round trip (camelCase JSON)"
    with check:
        assert "s3cret" not in caplog.text and "POST" in caplog.text, "logged, password masked"
    with pytest.raises(AssertionError, match="→ 201, expected"):
        response.expect_status(200)


# --- shared state


def test_shared_state_joins_its_state_and_switches_once_the_other_is_done(
    tmp_path: Path,
) -> None:
    resource = {"on": True}
    events: list[str] = []

    def run(name: str, state: bool, seconds: float) -> None:
        def write(value: bool) -> None:
            events.append(f"{name} switches")
            resource["on"] = value

        with shared_state.hold(tmp_path, "switch", state, lambda: resource["on"], write):
            events.append(f"{name} starts")
            time.sleep(seconds)
            events.append(f"{name} ends")

    first = threading.Thread(target=run, args=("first", True, 3))
    first.start()
    time.sleep(0.3)
    other = threading.Thread(target=run, args=("other", False, 0))
    other.start()
    time.sleep(0.3)
    same = threading.Thread(target=run, args=("same", True, 0))
    same.start()
    for thread in (first, other, same):
        thread.join(timeout=20)

    with check:
        assert events.index("same starts") < events.index("first ends"), "its state: joins at once"
    with check:
        assert events.index("other switches") > events.index("first ends"), "waits for the holders"
    with check:
        assert resource["on"] is False and events.count("other switches") == 1, "switched once"
