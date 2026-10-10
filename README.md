# python-selenium-framework-template

Starting point for a new UI-automation project: **Python + Selenium 4 + pytest** — a fresh browser
per test, page objects over standard elements declared like `@FindBy`, explicit waits only, test
data from JSON as fixtures, API preconditions with automatic cleanup, failure artifacts, logs per
test, local / Grid / CI runs in parallel — plus the Claude Code setup that drives onboarding and
test writing: the `web-automation` plugin from
[qa-automation-toolkit](https://github.com/FruNoman/qa-automation-toolkit) is enabled in
`.claude/settings.json`. This repo keeps only `framework-core` (the framework's rules) and
`.claude/site-map/` (the map of the app under test).

The same rules as the Java templates
([selenium-framework-template](https://github.com/FruNoman/selenium-framework-template),
[playwright-framework-template](https://github.com/FruNoman/playwright-framework-template)) —
carried by Python's own mechanisms, not translated Java: pytest fixtures instead of Spring scopes,
element descriptors instead of `@FindBy`, pytest-check instead of AssertJ, `xfail(strict=True)`
for known bugs. The test-data JSON (placeholders, camelCase keys) reads the same in all of them.

## Start a new project

1. Create a repo from this template, open it in Claude Code (accept the `web-automation` plugin).
2. Ask: *"onboard this project"* — `onboard-new-project` works in stages and stops for your go
   after each: discovery and interview → skeleton (env files, the example replaced by the app's
   entry page, green locally, on the Grid and like CI) → base architecture (login, API client,
   test data, cleanup, failure artifacts, each proven by one check in `tests/framework`).
3. Then, on request: pages (`add-page`), API clients (`add-api-client`), TMS suites
   (`import-tms-suite`), single tests (`new-web-test`), CI (`ci-setup`), a coverage map
   (`coverage-review`). Every place the template expects a change is marked `ONBOARD:`.

## What's inside

| Module | What |
|---|---|
| `autotests/elements/` | The standard elements, by ARIA roles and common markup: `Button`, `Input`, `CheckBox`, `RadioGroup`, `FileUpload`, `Calendar`; `SelectDropdown` / `ListDropdown` / `AriaDropdown` (portal listboxes, async search) / `MultiSelectDropdown` / `ReactSelectDropdown` / `Select2Dropdown` (jQuery select2 4.x — ⚠ proven on one app, Lightning Step, 2026-10-11) (one `Dropdown` protocol); `Table`, `Modal`, `Toasts`, `Tabs`, `Menu`, `Pagination`. Declared as class attributes of a page, found again on every use, every action logged. **Proven on every widget variant of the qa-playground `/widgets` gallery — 17 tests, Chrome and Firefox (2026-10-11).** |
| `autotests/pages/base_page.py` | `BasePage(browser)`: `path`, `is_loaded()`, `open()`, `get()`, `wait_loaded()`; the app's pages in `pages/<area>/` |
| `autotests/support/` | `Waits` (explicit only: `until`, `for_new_document`, `for_change`), failure artifacts |
| `autotests/data/` | `TestDataLoader` (JSON variants, per-env files, placeholders `{{uniqueTimestamp}}`, `{{inDays:3:yyyy-MM-dd}}`, Faker…), `TestData` models (pydantic), `data_fixture` / `texts_fixture` |
| `autotests/api/` | `ApiClient` (requests, DTOs in and out, secrets masked in the log; ONBOARD: auth; `post_form` for server-rendered forms), `forms.py` (`form_fields(html, form_id)` — what a browser would post — + `with_values`), `WebClient` (plain HTTP, redirects are answers) |
| `autotests/testdata/` | `TestDataRegistry` + `CleanupHandler`: what a test creates is deleted after it, also on failure; `sweep_stale` for killed runs |
| `autotests/auth/` | `User` (least privileged first), `Credentials` (from `resources/data/user-data.json`) |
| `autotests/plugin.py` | the pytest plugin: options, `settings`, `browser`, `user`, `authenticate`, data/texts/cleanup/api fixtures, logs per test, artifacts on failure and xfail |

Tests: `tests/framework` (the wiring on about:blank — no app or network needed; a project drops
it once its TMS cases cover the layers) and **the example** `tests/example` (Selenium's test form:
`WebFormPage` → `SubmittedPage`, data from `resources/data/web-form-data.json`) — template repo
only, removed right after cloning:

```bash
rm -rf tests/example resources/data/web-form-data.json
```

Soft assertions: `with check: assert …, "what"` (pytest-check). Known product bugs:
`@pytest.mark.xfail(strict=True, reason="…")` — runs every time, a fixed bug turns the run red.
Style: `ruff format` + `ruff check` (`make check`).

## Run

PyCharm: interpreter `.venv/bin/python` (made by `uv sync`), `src` marked as Sources Root —
otherwise every `autotests` import is red.

```bash
uv sync                                             # once: Python 3.14 + pinned dependencies
uv run pytest -n 4                                  # all, 4 browsers in parallel
uv run pytest tests/example/test_web_form.py::test_submit -n 0 --headed   # watch one
uv run pytest --browser firefox -n 4
GRID_URL=http://localhost:4444 uv run pytest --runner grid -n 4
make check                                          # style, like CI
```

Settings in layers, later wins: `config/application.yml` → `config/application-ci.yml` (`CI=true`)
→ `resources/env/<env>.yml` (`--env` / `TEST_ENV`, default `dev`) → env vars (`BASE_URL`,
`RUNNER`, `BROWSER`, `HEADLESS`, `GRID_URL`, `WAITS_TIMEOUT`) → options.

## CI

The framework is CI-agnostic: one command, config by env, results in `build/`
(`test-results/junit.xml`, `logs/tests/<test>.log`, `reports/failures/<test>/` — screenshot,
DOM, console, info), exit code = the result.

```bash
docker compose -f docker-compose.grid.yml up -d --wait     # Selenium 4.49 hub + Chrome + Firefox
docker compose -f docker-compose.grid.yml -f docker-compose.ci.yml up --build \
  --abort-on-container-exit --exit-code-from tests          # exactly what CI runs
```

`Dockerfile` = the runner image (also a Kubernetes Job). No CI file ships with the template: the
recipes (GitHub Actions, Jenkins, GitLab, Azure) are in the plugin's `ci-setup`. Grid images and
`selenium` in `pyproject.toml` carry the same version — bump both at once. `GRID_PORT` moves the
local Grid off 4444 when another project's Grid runs there.

Proven 2026-10-11: local Chrome and Firefox, Grid Chrome and Firefox, the CI compose — 14/14 each.

## Credentials

The tests' logins are test data — `resources/data/user-data.json`, a row per user — never env
vars or CI secrets; passwords never print (`SecretStr`). Tooling tokens (TMS API keys) live in a
git-ignored `.env.local`.
