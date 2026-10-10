"""What a test creates is deleted after it — also when it fails.

A fixture that creates something registers it *before* the request (a created-but-unparsed
response is still cleaned up), keyed by what identifies it without the response (a name or SKU the
fixture chose). After the test, every record is handed to the cleanup handler that knows its type,
newest first. A run killed midway leaves records behind: `sweep_stale` at the start of the next run
deletes the ones the naming prefix marks as test data and older than `stale_after`.

    @dataclass(frozen=True)
    class CreatedOrder:
        number: str

    class OrderCleanup(CleanupHandler):
        handles = CreatedOrder
        def delete(self, record): orders_api.delete(record.number)   # 404 = already gone
        def sweep_stale(self, older_than): ...
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, ClassVar

log = logging.getLogger(__name__)


class CleanupHandler:
    handles: ClassVar[type]

    def delete(self, record: Any) -> None:
        raise NotImplementedError

    def sweep_stale(self, older_than: dt.timedelta) -> list[str]:
        """Deletes test data older than `older_than` left by killed runs; returns what it deleted.
        Compare ages in the app's DB/API time, not this machine's clock."""
        return []


class TestDataRegistry:
    """One test's created records (the `created` fixture)."""

    __test__ = False

    def __init__(self, handlers: list[CleanupHandler]) -> None:
        self._handlers = handlers
        self._records: list[Any] = []

    def register(self, record: Any) -> Any:
        self._records.append(record)
        return record

    def clean_up(self) -> list[str]:
        """Deletes everything registered, newest first; a failed delete is logged, the rest go on.
        Returns the failures."""
        failures = []
        while self._records:
            record = self._records.pop()
            handler = next((h for h in self._handlers if isinstance(record, h.handles)), None)
            if handler is None:
                failures.append(f"no cleanup handler for {type(record).__name__}")
                continue
            try:
                handler.delete(record)
                log.info("cleaned up %s", record)
            except Exception as e:
                failures.append(f"{record}: {e}")
                log.warning("cleanup of %s failed: %s", record, e)
        return failures


def sweep_stale(handlers: list[CleanupHandler], older_than: dt.timedelta) -> None:
    for handler in handlers:
        try:
            swept = handler.sweep_stale(older_than)
            if swept:
                log.info("swept %d stale %s: %s", len(swept), handler.handles.__name__, swept)
        except Exception as e:
            log.warning("sweep of %s failed: %s", handler.handles.__name__, e)
