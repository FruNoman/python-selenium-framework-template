"""The framework's own rules a linter can't see (`make audit`, part of `make check`).

  pages/   no bare WebElement click / send_keys / script click / ActionChains (Selenium)
  tests/   (app tests, not tests/framework) every assert carries its message; no True/False
           slot in a compared tuple; no fixture in a test module; no conftest importing another's
  pages/   a module over MAX_PAGE_LINES lines
A line that must stay carries `# audit: ok <why>`. Exit 1 when anything is found.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "src" / "autotests" / "pages"
TESTS = ROOT / "tests"
MAX_PAGE_LINES = 500
_OK = "# audit: ok"
_BARE_ACTION = re.compile(
    r"find_elements?\(.*\)(\[[^\]]*\])?\.(click|send_keys)\(|execute_script\(.*\.click\(\)|ActionChains\("
)


def _ok(lines: list[str], lineno: int) -> bool:
    return _OK in lines[lineno - 1]


def _pages() -> list[str]:
    found = []
    for path in sorted(PAGES.rglob("*.py")):
        lines = path.read_text().splitlines()
        rel = path.relative_to(ROOT)
        if len(lines) > MAX_PAGE_LINES:
            found.append(f"{rel}: {len(lines)} lines — split the page (> {MAX_PAGE_LINES})")
        for number, line in enumerate(lines, 1):
            if _BARE_ACTION.search(line) and not _ok(lines, number):
                found.append(f"{rel}:{number}: acts around the elements — use an element")
    return found


def _bool_slot(node: ast.expr) -> bool:
    return isinstance(node, ast.Tuple) and any(
        isinstance(e, ast.Constant) and isinstance(e.value, bool) for e in node.elts
    )


def _is_fixture(dec: ast.expr) -> bool:
    target = dec.func if isinstance(dec, ast.Call) else dec
    return isinstance(target, ast.Attribute) and target.attr == "fixture"


def _tests() -> list[str]:
    found = []
    for path in sorted(TESTS.rglob("*.py")):
        if "framework" in path.relative_to(TESTS).parts:
            continue  # the framework's own self-tests, not app tests
        text = path.read_text()
        lines = text.splitlines()
        rel = path.relative_to(ROOT)
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert) and not _ok(lines, node.lineno):
                if node.msg is None:
                    found.append(f"{rel}:{node.lineno}: assert without its message")
                if isinstance(node.test, ast.Compare) and (
                    _bool_slot(node.test.left) or any(_bool_slot(c) for c in node.test.comparators)
                ):
                    found.append(f"{rel}:{node.lineno}: True/False slot in a compared record")
            if (
                path.name.startswith("test_")
                and isinstance(node, ast.FunctionDef)
                and any(_is_fixture(d) for d in node.decorator_list)
                and not _ok(lines, node.lineno)
            ):
                found.append(
                    f"{rel}:{node.lineno}: fixture in a test module — move it to a conftest"
                )
            if (
                path.name == "conftest.py"
                and isinstance(node, ast.ImportFrom)
                and (node.module or "").endswith("conftest")
                and not _ok(lines, node.lineno)
            ):
                found.append(
                    f"{rel}:{node.lineno}: imports another conftest — use the common parent"
                )
    return found


def main() -> int:
    found = (_pages() if PAGES.exists() else []) + (_tests() if TESTS.exists() else [])
    for line in found:
        print(line)
    print(f"audit: {len(found)} finding(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
