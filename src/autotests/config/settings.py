"""The run's settings: YAML defaults, the CI layer, the environment's file, env vars, CLI options.

One immutable `Settings` per run (the `settings` fixture). Nothing reads os.environ elsewhere.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[3]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BrowserSettings(_Frozen):
    name: Literal["chrome", "firefox"] = "chrome"
    headless: bool = True
    window: tuple[int, int] = (1440, 900)


class GridSettings(_Frozen):
    url: str = "http://localhost:4444"


class WaitSettings(_Frozen):
    timeout: float = 10
    poll: float = 0.1
    page_load: float = 30


class DirSettings(_Frozen):
    dir: str


class BaseSettings(_Frozen):
    url: str


class Settings(_Frozen):
    env: str = "dev"
    runner: Literal["local", "grid"] = "local"
    ci: bool = False
    base: BaseSettings
    browser: BrowserSettings = BrowserSettings()
    grid: GridSettings = GridSettings()
    waits: WaitSettings = WaitSettings()
    artifacts: DirSettings = DirSettings(dir="build/reports/failures")
    logs: DirSettings = DirSettings(dir="build/logs")
    data: DirSettings = DirSettings(dir="resources/data")

    def path(self, relative: str) -> Path:
        """A path from the settings, relative to the project's root."""
        return (ROOT / relative).resolve()


# env var → the setting it overrides (a dotted path)
ENV_OVERRIDES = {
    "TEST_ENV": "env",
    "BASE_URL": "base.url",
    "RUNNER": "runner",
    "BROWSER": "browser.name",
    "HEADLESS": "browser.headless",
    "GRID_URL": "grid.url",
    "WAITS_TIMEOUT": "waits.timeout",
}


def _merge(base: dict[str, Any], top: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in top.items():
        out[key] = (
            _merge(out[key], value)
            if isinstance(value, dict) and isinstance(out.get(key), dict)
            else value
        )
    return out


def _yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {} if path.exists() else {}


def _set(tree: dict[str, Any], dotted: str, value: Any) -> None:
    *parents, leaf = dotted.split(".")
    for key in parents:
        tree = tree.setdefault(key, {})
    tree[leaf] = value


def load_settings(
    cli: dict[str, Any] | None = None, environ: Mapping[str, str] | None = None
) -> Settings:
    """Layers, later wins: application.yml, application-ci.yml (CI=true), resources/env/<env>.yml,
    env vars, CLI options (dotted keys: {"env": "stage", "browser.headless": False})."""
    env_vars: Mapping[str, str] = os.environ if environ is None else environ
    cli = cli or {}
    ci = env_vars.get("CI", "").lower() in ("1", "true", "yes")
    tree = _yaml(ROOT / "config" / "application.yml")
    if ci:
        tree = _merge(tree, _yaml(ROOT / "config" / "application-ci.yml"))
    env = cli.get("env") or env_vars.get("TEST_ENV") or tree.get("env", "dev")
    env_file = ROOT / "resources" / "env" / f"{env}.yml"
    if not env_file.exists():
        raise FileNotFoundError(f"No environment '{env}': {env_file} is missing")
    tree = _merge(tree, _yaml(env_file))
    for var, dotted in ENV_OVERRIDES.items():
        if env_vars.get(var):
            _set(tree, dotted, env_vars[var])
    for dotted, value in cli.items():
        if value is not None:
            _set(tree, dotted, value)
    tree["env"], tree["ci"] = env, ci
    return Settings.model_validate(tree)
