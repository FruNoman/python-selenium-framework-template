"""The standard elements — pages declare these, never raw WebElements."""

from autotests.elements.composite import Menu, Modal, Pagination, Table, Tabs, Toasts
from autotests.elements.controls import Button, Calendar, CheckBox, FileUpload, Input, RadioGroup
from autotests.elements.core import Element, text_of
from autotests.elements.dropdown import (
    AriaDropdown,
    Dropdown,
    ListDropdown,
    MultiSelectDropdown,
    ReactSelectDropdown,
    Select2Dropdown,
    SelectDropdown,
)

__all__ = [
    "AriaDropdown",
    "Button",
    "Calendar",
    "CheckBox",
    "Dropdown",
    "Element",
    "FileUpload",
    "Input",
    "ListDropdown",
    "Menu",
    "Modal",
    "MultiSelectDropdown",
    "Pagination",
    "RadioGroup",
    "ReactSelectDropdown",
    "Select2Dropdown",
    "SelectDropdown",
    "Table",
    "Tabs",
    "Toasts",
    "text_of",
]
