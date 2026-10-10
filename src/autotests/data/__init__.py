"""Test data: models from JSON variants, the app's texts, placeholders."""

from autotests.data.fixtures import data_fixture, texts_fixture
from autotests.data.loader import TestDataLoader, variant_names
from autotests.data.models import TestData
from autotests.data.placeholders import register_resolver

__all__ = [
    "TestData",
    "TestDataLoader",
    "data_fixture",
    "register_resolver",
    "texts_fixture",
    "variant_names",
]
