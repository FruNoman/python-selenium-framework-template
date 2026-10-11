"""The app's fixed texts — resources/data/ui-texts.json, one typed model per area (its `area` key):

    class OrdersTexts(UiTexts):     # ui-texts.json {"default": {"orders": {"almostDone": …}}}
        area = "orders"
        almost_done: str

    orders_texts = texts_fixture(OrdersTexts)       # tests/conftest.py
    def test_x(..., orders_texts: OrdersTexts): …   # pyright knows every name

A key missing in the JSON or a typo in it fails at the first load (`TestData` refuses unknown keys).
"""

from __future__ import annotations

from typing import ClassVar

from autotests.data.models import TestData


class UiTexts(TestData):
    area: ClassVar[str]
    """The area's key in ui-texts.json."""
