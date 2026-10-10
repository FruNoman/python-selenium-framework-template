"""Evidence of a failed test, as plain files any CI can publish — no reporter needed:
<artifacts.dir>/<test>/screenshot.png, page.html, console.log, info.txt."""

from __future__ import annotations

import datetime as dt
import logging
import re
import threading
from pathlib import Path

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

log = logging.getLogger(__name__)


def folder_name(nodeid: str) -> str:
    """tests/example/test_web_form.py::test_submit[x] → test_web_form.test_submit[x]"""
    path, _, name = nodeid.partition("::")
    return re.sub(r"[^\w.\[\]-]+", "_", f"{Path(path).stem}.{name.replace('::', '.')}")


def save(driver: WebDriver, folder: Path, nodeid: str, failure: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    _try("screenshot", lambda: driver.save_screenshot(str(folder / "screenshot.png")))
    _try("page.html", lambda: (folder / "page.html").write_text(driver.page_source))
    _try("console.log", lambda: (folder / "console.log").write_text(_console(driver)))
    info = [f"test:     {nodeid}", f"failure:  {failure}"]
    _try("url", lambda: info.append(f"url:      {driver.current_url}"))
    _try("title", lambda: info.append(f"title:    {driver.title}"))
    caps = driver.capabilities
    info += [
        f"browser:  {caps.get('browserName')} {caps.get('browserVersion')}",
        f"thread:   {threading.current_thread().name}",
        f"time:     {dt.datetime.now().isoformat(timespec='seconds')}",
    ]
    (folder / "info.txt").write_text("\n".join(info) + "\n")
    log.info("failure artifacts → %s", folder)
    return folder


def _console(driver: WebDriver) -> str:
    """Chrome's console (goog:loggingPrefs), Firefox's from the BiDi log the driver factory keeps —
    local and Grid alike."""
    recorded = getattr(driver, "autotests_console", None)
    if recorded is not None:
        return "".join(f"{m}\n" for m in recorded) or "(empty)\n"
    try:
        entries = driver.execute("getLog", {"type": "browser"})["value"]
    except WebDriverException:
        return "(the browser console isn't available for this browser)\n"
    return "".join(f"{e.get('level')} {e.get('message')}\n" for e in entries) or "(empty)\n"


def _try(what: str, action) -> None:
    try:
        action()
    except Exception as e:
        log.warning("failure artifact %s not saved: %s", what, e)


__all__ = ["folder_name", "save"]
