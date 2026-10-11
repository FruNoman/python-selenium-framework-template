"""A shared resource of the environment in a state for a test — a global switch every user sees.

Tests needing the same state run in parallel; a test needing another state waits until they are
done, then sets it once for its own turn. Across xdist workers through a lock file per resource:
holders of a state keep a shared lock, the one that changes it takes the exclusive one.

    @pytest.mark.shared_state("medication_v2_feature", False)
    def test_LS82_...(...): ...

The project overrides the `shared_state_setter` fixture (tests/conftest.py): key → (read, write)
through the app's API. It only orders this machine's runs: another run on the environment (CI, a
colleague) can still flip the switch — check the state before the step that depends on it, and
read a failure there as that first (Lightning Step's medication_v2_feature, lab9 2026-10-11).
"""

from __future__ import annotations

import fcntl
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@contextmanager
def hold(
    folder: Path, key: str, state: Any, read: Callable[[], Any], write: Callable[[Any], None]
) -> Iterator[None]:
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / f"{key}.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        if read() != state:  # set by another run, or ours ended with the other state
            fcntl.flock(lock, fcntl.LOCK_UN)
            fcntl.flock(lock, fcntl.LOCK_EX)  # waits until the other state's tests are done
            if read() != state:
                log.info("shared state: %s → %s", key, state)
                write(state)
            fcntl.flock(lock, fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
