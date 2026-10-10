"""The base of the test-data models."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class TestData(BaseModel):
    """Base of every `<Area>Data` model: frozen, unknown keys refused (a typo in the JSON fails
    loudly), and its repr is the class name only — the values (unique, maybe secret) never reach
    test names or logs. The JSON keeps the camelCase every stack's data files use
    ("optionValue"), the model the Python name (`option_value`)."""

    __test__ = False
    model_config = ConfigDict(
        frozen=True, extra="forbid", alias_generator=to_camel, populate_by_name=True
    )

    def __repr__(self) -> str:
        return type(self).__name__

    __str__ = __repr__
