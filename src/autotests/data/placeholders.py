"""Placeholders of the test-data JSON — every occurrence gets its own value. The same syntax as the
Java stacks, so a data file reads the same in any of the project's frameworks:

| Placeholder | Value |
|---|---|
| {{today:<pattern>}}, {{tomorrow:…}}, {{yesterday:…}}, {{inDays:N:<pattern>}},
  {{inMonths:N:<pattern>}} | a date; the pattern in Java's notation (yyyy-MM-dd, MM/dd/yyyy) |
| {{random:N}} | an N-digit number, no leading zero |
| {{text:N}} | N letters — for length limits |
| {{uuid}}, {{timestamp}}, {{uniqueTimestamp}} | unique values; uniqueTimestamp never twice in a
  run — for values that must differ between parallel tests |
| {{firstname}}, {{lastname}}, {{company}}, {{word}} | Faker |
| {{<name>}} of a registered resolver | its value ({{freeSku}}) — `register_resolver` |
"""

from __future__ import annotations

import calendar
import datetime as dt
import os
import random
import re
import string
import threading
import time
import uuid
from collections.abc import Callable

from faker import Faker

_faker = Faker("en_US")
_resolvers: dict[str, Callable[[], str]] = {}

_DATE = re.compile(r"\{\{(today|tomorrow|yesterday|inDays:(-?\d+)|inMonths:(-?\d+)):([^}]+)}}")
_RANDOM = re.compile(r"\{\{random:(\d+)}}")
_TEXT = re.compile(r"\{\{text:(\d+)}}")

# Java DateTimeFormatter letters → strftime, longest first
_JAVA_TOKENS = [
    ("yyyy", "%Y"),
    ("yy", "%y"),
    ("MMMM", "%B"),
    ("MMM", "%b"),
    ("MM", "%m"),
    ("dd", "%d"),
    ("EEEE", "%A"),
    ("EEE", "%a"),
    ("HH", "%H"),
    ("hh", "%I"),
    ("mm", "%M"),
    ("ss", "%S"),
    ("a", "%p"),
]
_SINGLE = {"M": lambda d: str(d.month), "d": lambda d: str(d.day)}

_lock = threading.Lock()
_last_stamp = [0]


def register_resolver(name: str, resolve: Callable[[], str]) -> None:
    """{{name}} → resolve() — e.g. a SKU checked free through the API. Must not load test data."""
    _resolvers[name] = resolve


def unique_timestamp() -> str:
    """Epoch millis, never the same twice in the run: unique within this process, and an xdist
    worker's number appended ("…3" for gw3) keeps parallel processes apart."""
    with _lock:
        now = max(int(time.time() * 1000), _last_stamp[0] + 1)
        _last_stamp[0] = now
    worker = os.environ.get("PYTEST_XDIST_WORKER", "")
    return f"{now}{worker[2:]}" if worker.startswith("gw") else str(now)


def format_java(date: dt.date | dt.datetime, pattern: str) -> str:
    """A date formatted by a Java DateTimeFormatter pattern (the common letters)."""
    out, i = [], 0
    while i < len(pattern):
        if pattern[i] == "'":  # quoted literal
            end = pattern.index("'", i + 1)
            out.append(pattern[i + 1 : end])
            i = end + 1
            continue
        for token, directive in _JAVA_TOKENS:
            if pattern.startswith(token, i):
                out.append(date.strftime(directive))
                i += len(token)
                break
        else:
            char = pattern[i]
            out.append(_SINGLE[char](date) if char in _SINGLE else char)
            i += 1
    return "".join(out)


def _date(match: re.Match[str]) -> dt.date:
    today = dt.date.today()
    kind = match.group(1)
    if kind == "today":
        return today
    if kind == "tomorrow":
        return today + dt.timedelta(days=1)
    if kind == "yesterday":
        return today - dt.timedelta(days=1)
    if match.group(2) is not None:
        return today + dt.timedelta(days=int(match.group(2)))
    months = today.month - 1 + int(match.group(3))
    year, month = today.year + months // 12, months % 12 + 1
    return today.replace(
        year=year, month=month, day=min(today.day, calendar.monthrange(year, month)[1])
    )


def _random_digits(n: int) -> str:
    return str(random.randint(1, 9)) + "".join(random.choices(string.digits, k=n - 1))


def process(text: str) -> str:
    for name, resolve in _resolvers.items():
        text = re.sub(re.escape("{{" + name + "}}"), lambda _, r=resolve: r(), text)
    text = _DATE.sub(lambda m: format_java(_date(m), m.group(4)), text)
    text = _RANDOM.sub(lambda m: _random_digits(int(m.group(1))), text)
    text = _TEXT.sub(
        lambda m: "".join(random.choices(string.ascii_lowercase, k=int(m.group(1)))), text
    )
    simple = {
        "uuid": lambda: str(uuid.uuid4()),
        "timestamp": lambda: str(int(time.time() * 1000)),
        "uniqueTimestamp": unique_timestamp,
        "firstname": _faker.first_name,
        "lastname": _faker.last_name,
        "company": _faker.company,
        "word": _faker.word,
    }
    for name, value in simple.items():
        text = re.sub(re.escape("{{" + name + "}}"), lambda _, v=value: v(), text)
    return text
