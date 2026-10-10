---
name: framework-core
description: The rules of this Python + Selenium + pytest framework core — a fresh browser per test (the `browser` fixture), page objects created per test and returned by the actions that lead to them, the standard elements declared as class attributes (descriptors — tables, dropdowns, checkboxes… no new element classes unless asked), explicit waits only (implicit 0), JSON test data reaching tests as fixtures, API preconditions with automatic cleanup, failure artifacts, known bugs as xfail(strict=True), settings in layers (YAML, env file, env vars, options). Use whenever writing or changing pages, elements, tests, test data, browser config or settings.
---

# Framework core — the rules (python-selenium)

The same rules as the Java stacks (selenium-framework-template), carried by Python's own
mechanisms: what a Java project does with Spring scopes, `@FindBy` and TestNG, this one does with
pytest fixtures, element descriptors and markers. Workflow (writing and running tests, login,
onboarding, site map) comes from the `web-automation` plugin enabled in `.claude/settings.json`.

## Which skill when — load it before the work, not after

The routing table lives in the plugin: **`web-automation:which-skill`** — which skill covers which
task, which subagent does the bulk reading. Not copied here: a copy per project drifts. This file
holds the framework's **rules**; the plugin the **workflow**.

**Writing or changing a test, or its data → load `web-automation:test-data` first, always.** Data
reaches a test as a fixture named after it (`web_form_data`), the app's texts as `<area>_texts`;
no `loader.load(...)` in a test body.

## Browser

- `browser` (function scope): **a fresh browser per test**, quit after it — no cookies, storage or
  windows leak between tests. `Browser(driver, settings, waits)` is what pages take.
- `driver/factory.py`: local Chrome/Firefox or `webdriver.Remote` on the Grid
  (`--runner grid`, `GRID_URL`). Implicit wait 0 always. On a Grid, Chrome gets CDP focus
  emulation (parallel sessions on one node take each other's focus — focus/blur widgets flake
  otherwise). Firefox's console comes over BiDi (`enable_bidi`); the Grid's nodes need
  `SE_NODE_GRID_URL` = the URL clients use.
- Logged in before the test starts: the `authenticate(browser, user)` fixture (ONBOARD —
  `login-strategies`: a session cookie or token injected, never the login form outside the
  login-flow tests). The user: `@pytest.mark.as_user(User.ADMIN)`, default the least privileged
  `User.USER` — an admin sees everything, a missing permission check would pass unnoticed.
- Cookie injection: land on a cheap page of the app's origin first (`favicon.ico`), then
  `add_cookie` **without `domain`** (host-only, as the app sets it): Firefox refuses
  `domain=localhost` ("unable to set cookie"), Chrome takes either (qa-playground 2026-10-11).

## Settings

Layers, later wins: `config/application.yml` → `config/application-ci.yml` (`CI=true`) →
`resources/env/<env>.yml` (`--env` / `TEST_ENV`, default `dev`) → env vars (`BASE_URL`, `RUNNER`,
`BROWSER`, `HEADLESS`, `GRID_URL`, `WAITS_TIMEOUT`) → options (`--env`, `--runner`, `--browser`,
`--headed`). One frozen `Settings` per run (the `settings` fixture); nothing else reads
`os.environ`. An env file holds URLs and non-secret per-env settings; logins are test data.

## Pages

- `BasePage(browser)`: `path` (relative to `base.url`), `is_loaded()` (override with the page's
  own content when the URL isn't enough), `open()` (navigate + wait loaded), `get()` (open unless
  shown), `wait_loaded()`, `element(by, value, name, cls)` for a locator built at run time,
  `js(...)` only where WebDriver has no call.
- **A page object lives for one test**: created from the test's `browser`, never cached, no state
  in class attributes other than element declarations.
- **The test talks to the page, never to its elements**: elements are `_private` class
  attributes; one method per user action **whatever its outcome** (`save()`, not `save_ok()` /
  `save_rejected()`) — fluent (`return self`) when it stays, the next page when it leads there
  (`submit() -> SubmittedPage`), nothing when the landing depends on the data (the test reads
  the page it holds); reads return values or page records (`list[Order]`, a dataclass), never
  `dict` rows.
- **Pages come from the actions that lead to them**: a test takes its entry page from a fixture
  (`web_form_page`, opened) and every other page as a local variable from the action
  (`profile_page = login_page.sign_in(user)`), so the navigation reads in the test.
- A page is named after its class: `web_form_page`, `orders_page` — never `page`, `form`.
- An action that loads a new document waits for it: `self.waits.for_new_document(self._save.click)`
  — also when the URL stays the same (a form drawn again with errors).

## Elements

- Declared as class attributes — `_email = Input(By.ID, "email")` — Python's `@FindBy`: found
  again on every use (no stale references), each action logged as `[Page._email] type '…'`.
  `part(by, value, name, cls)` finds inside an element; `wrap(web_element, name, cls)` turns one
  found at run time (a row, a cell) into an element (`table.wrap(cell, "row menu", Menu)`).
- The standard set (`autotests.elements`, proven on every widget variant of the qa-playground
  `/widgets` gallery in Chrome and Firefox, 2026-10-11): `Button`, `Input`, `CheckBox`,
  `RadioGroup`, `FileUpload`, `Calendar`, `SelectDropdown`, `ListDropdown`, `AriaDropdown`,
  `MultiSelectDropdown`, `ReactSelectDropdown`, `Select2Dropdown` (declared on the hidden `<select>`;
  ⚠ proven on one app) (one `Dropdown` protocol), `Table`, `Modal`,
  `Toasts`, `Tabs`, `Menu`, `Pagination`. By ARIA roles and common markup, so they fit most apps.
- **No new element classes unless the user asks** — a widget none fits: a subclass overriding its
  CSS hooks (`ListDropdown.toggle_css`), or stop and ask. Screen-specific reading (a badge, a
  row's checkbox) lives in the page.
- React apps: `Input.type_kept` (a field drawn again while typed into), `Button.click_until(what,
  done)` (a click the app loses or a toast covers), `CheckBox` clicks a 0 px box's label or cell.
  A fix the elements lack, seen in a second page, goes into the element — not a loop per page.
- Passwords: `Input.type` / `clear_and_type` take a `SecretStr` and log `***` — pass the
  credential's `SecretStr` as is, never `.get_secret_value()` (the log would hold it; lab9).
- Text: `text_of(e)` / `element.text()` = textContent with whitespace collapsed (&nbsp; too), not
  changed by CSS text-transform, also for hidden elements.
- Name clashes: an element class's public names are its API (`Input.value()`); the base keeps its
  locator private (`_by`, `_using`).

## Waits

- Explicit only — `self.waits.until(condition, "what was awaited")`: the message is the failure's
  first line. **No `time.sleep`** in pages or tests.
- Wait for what *your* action produces, not for "loaded": `for_new_document(action)`,
  `for_change(state, action)` (sort/page that may redraw in place or navigate), an element's
  `wait_visible()` / `wait_gone()`. An async list drawn twice (placeholder, then data) is waited
  for by the state the action produces.
- Timeouts in `waits.*` (YAML); CI doubles them.

## Package layout — the framework in `autotests/`, the app by area

```
src/autotests/          config/ driver/ support/ elements/ pages/base_page.py data/ api/client.py
                        auth/ testdata/core.py plugin.py          ← the framework (ported as is)
src/autotests/pages/<area>/        the app's pages              (orders/order_page.py)
src/autotests/api/<area>/          the app's API clients + dto.py
src/autotests/testdata/<area>/     fixtures + cleanup handlers of what tests create
tests/<tms-suite>/…/test_<leaf>.py  tests, mirroring the TMS tree
tests/steps/<area>.py              flows several tests need as preconditions
tests/conftest.py                  page, data and texts fixtures; cleanup_handlers; authenticate
resources/env/ resources/data/ resources/files/
```

A package past ~10 modules splits by area; a module past ~500 lines splits by screen.

## Test data, API, cleanup

- Data: `resources/data/<model>.json` (`OrderData` ← `order-data.json`), variants by name; the
  main one is `"default"`; `resources/data/<env>/<file>` replaces the shared file whole.
  Placeholders (`{{uniqueTimestamp}}`, `{{inDays:3:yyyy-MM-dd}}`, `{{text:N}}`, Faker…) — the same
  syntax as the Java stacks, re-resolved on every load. Models extend `TestData` (pydantic:
  frozen, unknown keys refused, camelCase JSON keys → snake_case fields, repr = the class name
  only; secrets `SecretStr`).
- In tests: `order_data = data_fixture(OrderData)` in conftest → `def test_x(..., order_data)`;
  another variant: `@pytest.mark.parametrize("order_data", ["prn"], indirect=True)`; a data table:
  `parametrize(..., variant_names(OrderData), indirect=True)` — the test id carries the variant
  name. The app's texts: `ui-texts.json` → `orders_texts = texts_fixture("orders")`.
- Logins: `resources/data/user-data.json` (row per `User`, lower case) through `credentials(user)`
  — never env vars, CI secrets or YAML. Tooling tokens (TMS, CI) only in a git-ignored
  `.env.local`.
- API: `api/<area>/<x>_api.py` takes the request DTO (pydantic, `model_dump(by_alias=True)`) and
  returns parsed responses (`ApiResponse.expect_status(201).as_model(OrderResponse)`) — never a
  dict built field by field; bodies logged with secrets masked. `api.as_user(user)` — ONBOARD
  the app's auth. `WebClient` for plain HTTP to the web app (redirects are answers).
- Preconditions through the API, not through other screens. What a test creates is registered
  **before** the request (`created.register(CreatedOrder(number))`) and deleted after the test
  by its `CleanupHandler` — also when the test fails; `sweep_stale` deletes what a killed run left
  (the naming prefix + age in the app's time). Never delete by hand in a test.

## Failures

`build/reports/failures/<test>/`: `screenshot.png`, `page.html`, `console.log`, `info.txt` — for
a failed test **and for a known bug failing as expected** (xfail): the proof it fails *because of*
the bug, not a locator. `build/logs/tests/<test>.log` — one log per test; `build/test-results/
junit.xml` for CI and the TMS.

## Tests

- Test code mirrors the TMS tree: top-level suite → package, leaf suite → `test_<leaf>.py`, case →
  `def test_<id>_<title>` — **TestRail** `test_C123_…` (trcli `parse_junit --case-matcher name`
  reads it from junit.xml), **Qase** read-only `test_LS83_add_new_diagnosis` (+ the id in the
  docstring), a writable Qase: its pytest reporter. A test without a case has no id; never invent
  one.
- **Soft assertions — `pytest-check`**: one `with check: assert …, "what"` per expectation, so a
  run reports every broken one of the case; a plain `assert` only where going on is pointless (a
  precondition failed, a known bug blocking the next steps). The message says what was expected.
- **An assertion only checks**: no action or navigation inside `assert` — the action is its own
  statement before it.
- **Known product bugs**: `@pytest.mark.xfail(strict=True, reason="<the finding>")` — the test
  runs every time: XFAIL while the bug is there (with failure artifacts as proof), and a fixed bug
  turns the run **red** (XPASS, `xfail_strict = true`) — drop the marker then. Never `skip` it,
  never loosen the assertion. Prove it before marking: run it, read the artifacts — it must fail on
  the bug, not on a locator or data.
- **A test module holds only tests** (and its imports): fixtures in conftest.py, flows tests repeat
  as preconditions in `tests/steps/<area>.py` (complete actions of the positive flow ending in a
  stable state, named verb + object — `create_order`), a step checks with a plain `assert`.
- Steps a case repeats from another automated case are its precondition: done through a fixture
  or a step, not checked again.
- **Parallel = processes** (`-n N`, pytest-xdist): no shared state between tests anyway; a value
  that must be unique across workers: `{{uniqueTimestamp}}` (carries the worker number). A resource
  of the environment several tests switch (a feature flag): a file lock per resource, not a module
  global — ask before adding one.
- `tests/framework` is scaffolding (the wiring on about:blank + onboarding's layer proofs): it goes
  once the project's TMS cases cover the layers.

## Code style — the formatter's

`ruff format` (Black style, 100 columns) and `ruff check` (pyflakes, isort, bugbear, pyupgrade,
naming) — `make check` / `uv run ruff check . && uv run ruff format --check .`. Type hints on public
functions; `from __future__ import annotations`; docstrings say *why*, in the project's words.
Blank lines between Arrange / Act / Assert and around each `with check:`. Python edits through
the editor (Edit tool), never through sed/heredoc scripts on source files.

## Running locally

```bash
uv run pytest -n 4                                     # all, 4 browsers in parallel
uv run pytest tests/orders/test_orders.py::test_x -n 0 --headed   # watch one
uv run pytest --runner grid -n 4                       # on the Grid (GRID_URL)
uv run pytest --browser firefox
docker compose -f docker-compose.grid.yml -f docker-compose.ci.yml up --build \
  --abort-on-container-exit --exit-code-from tests     # exactly like CI
```

## CI contract (details: `ci-setup` in the plugin)

One command (`uv run pytest -n $TESTS_THREADS`), config by env (`CI=true`, `RUNNER=grid`,
`GRID_URL`, `TEST_ENV`, `BASE_URL`), browsers only in the Grid (`docker-compose.grid.yml`, Selenium
pinned with `selenium` in pyproject — bump together), results in `build/` (junit.xml, logs,
failure artifacts), exit code = the result, `Dockerfile` = the runner image.

## This project

ONBOARD: the app, its environments, its TMS, the decisions the onboarding records — in
`.claude/project-profile.md`; app facts in `.claude/site-map/`.
