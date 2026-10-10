"""The framework's pytest plugin (pyproject: `-p autotests.plugin`): options, fixtures, hooks.

Fixtures a test (or a page/data fixture in conftest.py) asks for:
  settings          the run's Settings (session)
  browser           one test's browser — a fresh one per test, quit after it — with settings, waits
  user              who the test runs as (`as_user(User.ADMIN)` mark; default: the first User)
  test_data_loader  JSON test data (session); data reaches tests through `data_fixture(...)`
  ui_texts          the app's fixed texts (session); per area through `texts_fixture(...)`
  created           what this test creates, deleted after it (cleanup handlers: `cleanup_handlers`)
  api               the app's API client (session)

Overridable in conftest.py: `cleanup_handlers` (the app's CleanupHandlers), `authenticate`
(how a browser is logged in as a user — ONBOARD: login-strategies).
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from autotests.api.client import ApiClient
from autotests.auth.users import Credentials, User
from autotests.config.settings import Settings, load_settings
from autotests.data.loader import TestDataLoader
from autotests.driver.factory import create_driver
from autotests.pages.base_page import Browser
from autotests.support import artifacts
from autotests.support.waits import Waits
from autotests.testdata.core import CleanupHandler, TestDataRegistry, sweep_stale

log = logging.getLogger("autotests")

_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-5s [%(name)s] %(message)s"


# --- options


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("autotests")
    group.addoption("--env", help="resources/env/<name>.yml (default: TEST_ENV, else dev)")
    group.addoption("--runner", choices=["local", "grid"], help="local browser or Selenium Grid")
    group.addoption("--browser", choices=["chrome", "firefox"])
    group.addoption("--headed", action="store_true", help="show the browser (watch one test)")


def pytest_configure(config: pytest.Config) -> None:
    cli = {
        "env": config.getoption("--env"),
        "runner": config.getoption("--runner"),
        "browser.name": config.getoption("--browser"),
        "browser.headless": False if config.getoption("--headed") else None,
    }
    config._autotests_settings = load_settings(cli)  # type: ignore[attr-defined]


# --- settings, logs


@pytest.fixture(scope="session")
def settings(pytestconfig: pytest.Config) -> Settings:
    return pytestconfig._autotests_settings  # type: ignore[attr-defined]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Iterator[None]:
    """One log file per test: <logs.dir>/tests/<test>.log."""
    settings: Settings = item.config._autotests_settings  # type: ignore[attr-defined]
    folder = settings.path(settings.logs.dir) / "tests"
    folder.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(folder / f"{artifacts.folder_name(item.nodeid)}.log", "w")
    handler.setFormatter(logging.Formatter(_FORMAT, "%H:%M:%S"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    item._autotests_log = handler  # type: ignore[attr-defined]
    log.info("▶ %s", item.nodeid)
    yield


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    handler = getattr(item, "_autotests_log", None)
    if handler is not None:
        logging.getLogger().removeHandler(handler)
        handler.close()


# --- the browser


@pytest.fixture
def browser(
    request: pytest.FixtureRequest,
    settings: Settings,
    user: User,
    authenticate: Callable[[Browser, User], None],
) -> Iterator[Browser]:
    """A fresh browser for this test — no cookies, storage or windows from another test —
    logged in as `user` by `authenticate`, quit after the test."""
    driver = create_driver(settings)
    browser = Browser(driver, settings, Waits(driver, settings.waits.timeout, settings.waits.poll))
    # for the failure artifacts: a page fixture failing in setup (its page never loaded) leaves
    # item.funcargs without "browser" — it is filled only once every fixture succeeded (lab9)
    request.node._autotests_browser = browser
    try:
        authenticate(browser, user)
        yield browser
    finally:
        driver.quit()


@pytest.fixture
def user(request: pytest.FixtureRequest) -> User:
    marker = request.node.get_closest_marker("as_user")
    return marker.args[0] if marker else next(iter(User))  # the least privileged


@pytest.fixture
def authenticate() -> Callable[[Browser, User], None]:
    """ONBOARD: log the browser in as the user without the login form (a session cookie or a
    token injected — the login-strategies skill); until then tests start logged out."""
    return lambda browser, user: None


@pytest.fixture(scope="session")
def credentials(test_data_loader: TestDataLoader) -> Callable[[User], Credentials]:
    """The login of a User — resources/data/user-data.json."""
    return lambda user: test_data_loader.load(Credentials, user.value, "user-data.json")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]) -> Iterator[None]:
    """A failed test — and a known bug failing as expected (xfail), the proof that it fails
    because of the bug — leaves its browser's evidence."""
    outcome = yield
    report: pytest.TestReport = outcome.get_result()
    failed = report.failed and report.when in ("setup", "call")
    expected_failure = report.when == "call" and hasattr(report, "wasxfail") and report.skipped
    browser = getattr(item, "_autotests_browser", None)
    if (failed or expected_failure) and isinstance(browser, Browser):
        settings: Settings = item.config._autotests_settings  # type: ignore[attr-defined]
        folder = settings.path(settings.artifacts.dir) / artifacts.folder_name(item.nodeid)
        failure = str(call.excinfo.value).splitlines()[0] if call.excinfo else "?"
        artifacts.save(browser.driver, folder, item.nodeid, failure)
    if report.when == "call":
        log.info(
            "%s %s (%.1f s)",
            "✔" if report.passed else "✘ XFAIL" if hasattr(report, "wasxfail") else "✘ FAIL",
            item.nodeid,
            report.duration,
        )


# --- test data


@pytest.fixture(scope="session")
def test_data_loader(settings: Settings) -> TestDataLoader:
    return TestDataLoader(settings)


@pytest.fixture(scope="session")
def ui_texts(settings: Settings) -> dict[str, Any]:
    """resources/data/ui-texts.json → its "default" variant: area → texts."""
    import json

    path = settings.path(settings.data.dir) / "ui-texts.json"
    return json.loads(path.read_text())["default"] if path.exists() else {}


@pytest.fixture(scope="session")
def cleanup_handlers() -> list[CleanupHandler]:
    """Override in conftest.py with the app's handlers (one per kind of record tests create)."""
    return []


@pytest.fixture(scope="session", autouse=True)
def _sweep_stale_test_data(cleanup_handlers: list[CleanupHandler], worker_id: str) -> None:
    """What a killed run left — once per run (the first xdist worker, or a run without xdist;
    `worker_id` is pytest-xdist's fixture)."""
    if worker_id in ("master", "gw0"):
        sweep_stale(cleanup_handlers, dt.timedelta(hours=2))


@pytest.fixture
def created(cleanup_handlers: list[CleanupHandler]) -> Iterator[TestDataRegistry]:
    registry = TestDataRegistry(cleanup_handlers)
    yield registry
    failures = registry.clean_up()
    if failures:
        log.warning("cleanup left records behind: %s", failures)


# --- API


@pytest.fixture(scope="session")
def api(settings: Settings) -> ApiClient:
    """ONBOARD: the API's own base URL when it differs from the web app's (an `api.url` setting)."""
    return ApiClient(settings.base.url)


def artifacts_dir(settings: Settings) -> Path:
    return settings.path(settings.artifacts.dir)
