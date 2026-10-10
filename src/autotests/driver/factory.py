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
    return options


def create_driver(settings: Settings) -> WebDriver:
    chrome = settings.browser.name == "chrome"
    options = _chrome_options(settings) if chrome else _firefox_options(settings)
    if settings.runner == "local":
        driver = webdriver.Chrome(options=options) if chrome else webdriver.Firefox(options=options)
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
    log.info(
        "browser %s %s on %s",
        settings.browser.name,
        driver.capabilities.get("browserVersion"),
        settings.runner,
    )
    return driver
