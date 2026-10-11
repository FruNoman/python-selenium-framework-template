"""A browser for one test: local Chrome/Firefox or a Selenium Grid session.

Every test gets its own browser (the `driver` fixture) — nothing leaks between tests: no cookies, no
storage, no open windows. Implicit wait stays 0: waits are explicit (support.waits).
"""

from __future__ import annotations

import logging

from selenium import webdriver
from selenium.webdriver.chromium.remote_connection import ChromiumRemoteConnection
from selenium.webdriver.remote.webdriver import WebDriver

from autotests.config.settings import Settings

log = logging.getLogger(__name__)


def _chrome_options(settings: Settings) -> webdriver.ChromeOptions:
    options = webdriver.ChromeOptions()
    if settings.browser.headless:
        options.add_argument("--headless=new")
    width, height = settings.browser.window
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--disable-search-engine-choice-screen")
    # the browser console for failure artifacts
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    return options


def _firefox_options(settings: Settings) -> webdriver.FirefoxOptions:
    options = webdriver.FirefoxOptions()
    if settings.browser.headless:
        options.add_argument("-headless")
    width, height = settings.browser.window
    options.add_argument(f"--width={width}")
    options.add_argument(f"--height={height}")
    # Firefox has no getLog: its console comes over WebDriver BiDi (webSocketUrl). On a Docker
    # Grid the nodes need SE_NODE_GRID_URL set to the URL clients use (docker-compose.grid.yml),
    # or the session's webSocketUrl points at the hub's container IP
    options.enable_bidi = True
    return options


def _record_console(driver: WebDriver) -> None:
    """Firefox: the console messages of the session, kept for the failure artifacts."""
    messages: list[str] = []
    driver.autotests_console = messages  # type: ignore[attr-defined]
    try:
        driver.script.add_console_message_handler(
            lambda m: messages.append(f"{getattr(m, 'level', '?')} {getattr(m, 'text', m)}")
        )
    except Exception as e:  # a Grid that hands out an unreachable webSocketUrl
        log.warning("no BiDi console for this session: %s", e)


def create_driver(settings: Settings) -> WebDriver:
    chrome = settings.browser.name == "chrome"
    options = _chrome_options(settings) if chrome else _firefox_options(settings)
    if settings.runner == "local":
        driver = (
            webdriver.Chrome(options=_chrome_options(settings))
            if chrome
            else webdriver.Firefox(options=_firefox_options(settings))
        )
    else:
        executor = (
            ChromiumRemoteConnection(settings.grid.url, "goog", "chrome")
            if chrome
            else settings.grid.url
        )
        driver = webdriver.Remote(command_executor=executor, options=options)
        if chrome:
            # several Chrome sessions on one Grid node take each other's window focus: a click in
            # one blurs the pages of the others, and focus/blur-driven widgets fail at random
            driver.execute(
                "executeCdpCommand",
                {"cmd": "Emulation.setFocusEmulationEnabled", "params": {"enabled": True}},
            )
    driver.implicitly_wait(0)
    driver.set_page_load_timeout(settings.waits.page_load)
    if not chrome:
        driver.set_window_size(*settings.browser.window)
        _record_console(driver)
    log.info(
        "browser %s %s on %s",
        settings.browser.name,
        driver.capabilities.get("browserVersion"),
        settings.runner,
    )
    return driver
