"""A shared resource of the environment in a state for a test — a global switch every user sees.

Tests needing the same state run in parallel; a test needing another state waits until they are
done, then sets it once for its own turn. Across xdist workers through a lock file per resource:
holders of a state keep a shared lock, the one that changes it takes the exclusive one.

    @pytest.mark.shared_state("medication_v2_feature", False)
    def test_LS82_...(...): ...

The project overrides the `shared_state_setter` fixture (tests/conftest.py): key → (read, write)
through the app's API. It only orders this machine's runs: another run on the environment (CI, a
colleague) can still flip the switch — check the state before the step that depends on it, and
read a failure there as that first.
"""

from __future__ import annotations

import fcntl
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_LOOK_AGAIN_SECONDS = 2


@contextmanager
def hold(
    folder: Path, key: str, state: Any, read: Callable[[], Any], write: Callable[[Any], None]
) -> Iterator[None]:
    """A shared lock while the resource is in `state`. A test needing another state doesn't queue
    for the exclusive lock (flock would keep it waiting while any holder runs — even after another
    waiter already set its state): it looks again every few seconds and either joins the holders
    or, when there are none, takes the exclusive lock just to switch."""
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / f"{key}.lock").open("a+") as lock:
        while True:
            fcntl.flock(lock, fcntl.LOCK_SH)
            if read() == state:  # this state's turn: run alongside its other holders
                break
            fcntl.flock(lock, fcntl.LOCK_UN)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:  # the other state's tests still run
                time.sleep(_LOOK_AGAIN_SECONDS)
                continue
            if read() != state:
                log.info("shared state: %s → %s", key, state)
                write(state)
            # not atomic: another state may switch in between — the loop reads again
            fcntl.flock(lock, fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
