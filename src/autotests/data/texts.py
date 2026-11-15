"""The app's fixed texts — resources/data/ui-texts.json, one typed model per area (its `area` key):

    class OrdersTexts(UiTexts):     # ui-texts.json {"default": {"orders": {"almostDone": …}}}
        area = "orders"
        almost_done: str

    orders_texts = texts_fixture(OrdersTexts)       # tests/conftest.py
    def test_x(..., orders_texts: OrdersTexts): …   # pyright knows every name

An area may have a file of its own instead — resources/data/ui-texts/<area>.json, the area's texts
as they would sit under its key (`ui-texts/orders.json` = {"almostDone": …}) — so branches adding
different areas never touch the same file. Both are read and merged; an area in both is an error.

A key missing in the JSON or a typo in it fails at the first load (`TestData` refuses unknown keys).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from autotests.data.models import TestData


class UiTexts(TestData):
    area: ClassVar[str]
    """The area's key in ui-texts.json (or the name of its ui-texts/<area>.json)."""


def load_ui_texts(data_dir: Path) -> dict[str, Any]:
    """Area → texts: ui-texts.json's "default" variant merged with every ui-texts/<area>.json."""
    single = data_dir / "ui-texts.json"
    texts: dict[str, Any] = json.loads(single.read_text())["default"] if single.exists() else {}
    for path in sorted((data_dir / "ui-texts").glob("*.json")):
        area = path.stem
        if area in texts:
            raise ValueError(f"UI texts area '{area}' is defined twice: ui-texts.json and {path}")
        texts[area] = json.loads(path.read_text())
    return texts
