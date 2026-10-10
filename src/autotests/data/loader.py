"""Test data from resources/data/*.json — no literals in tests.

A file holds named variants of one model: `WebFormData` ← web-form-data.json,
{"default": {...}, "second-option": {...}}. An environment's own values go to
resources/data/<env>/<file>, which wins over resources/data/<file>. Placeholders are resolved on
every load, so every test gets fresh unique values — load once per test, keep the object.

Models are pydantic models (validated, dates parsed, frozen); a model whose fields hold secrets
(passwords) marks them `SecretStr`, so they never print.
"""

from __future__ import annotations

import json
import logging
import re
from functools import cache
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from autotests.config.settings import Settings
from autotests.data import placeholders

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)


def file_of(model: type[BaseModel]) -> str:
    """WebFormData → web-form-data.json"""
    return re.sub(r"(?<!^)(?=[A-Z])", "-", model.__name__).lower() + ".json"


@cache
def _raw(path: Path) -> str:
    return path.read_text()


class TestDataLoader:
    __test__ = False  # not a test class, despite the name

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.path(settings.data.dir)

    def load(self, model: type[M], variant: str = "default", file: str | None = None) -> M:
        variants = self._variants(file or file_of(model))
        if variant not in variants:
            raise KeyError(f"No variant '{variant}' in {file or file_of(model)}: {list(variants)}")
        data = json.loads(placeholders.process(json.dumps(variants[variant])))
        log.debug("test data %s '%s'", model.__name__, variant)
        return model.model_validate(data)

    def load_all(self, model: type[M], file: str | None = None) -> list[M]:
        """Every variant in file order — the rows of a data table."""
        return [self.load(model, v, file) for v in self.variant_names(model, file)]

    def variant_names(self, model: type[BaseModel], file: str | None = None) -> list[str]:
        return list(self._variants(file or file_of(model)))

    def _variants(self, file: str) -> dict:
        for path in (self.root / self.settings.env / file, self.root / file):
            if path.exists():
                return json.loads(_raw(path))
        raise FileNotFoundError(f"No test data {self.settings.env}/{file} or {file} in {self.root}")


def variant_names(
    model: type[BaseModel], file: str | None = None, data_dir: Path | None = None
) -> list[str]:
    """The variant names at collection time — for `@pytest.mark.parametrize(..., indirect=True)`
    over a data table (the env's own file isn't known yet here: the shared file's names)."""
    from autotests.config.settings import ROOT

    path = (data_dir or ROOT / "resources" / "data") / (file or file_of(model))
    return list(json.loads(path.read_text()))
