"""The app's server-rendered forms posted over HTTP the way a browser posts them: every field's
default (hidden ids and tokens the page generates, selected options, checked boxes) and then the
test's own values on top — not a hand-built list of 180 fields that drifts from the page."""

from __future__ import annotations

from html.parser import HTMLParser


class _FormFields(HTMLParser):
    def __init__(self, form_id: str) -> None:
        super().__init__(convert_charrefs=True)
        self.form_id = form_id
        self.inside = False
        self.fields: list[tuple[str, str]] = []
        self._select: str | None = None
        self._options: list[tuple[str, bool]] = []
        self._textarea: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag == "form":
            self.inside = a.get("id") == self.form_id
            return
        if not self.inside:
            return
        name = a.get("name")
        if tag == "input" and name:
            kind = a.get("type", "text").lower()
            if kind in ("button", "submit", "reset", "image", "file"):
                return
            if kind in ("checkbox", "radio") and "checked" not in a:
                return
            self.fields.append((name, a.get("value", "on" if kind == "checkbox" else "")))
        elif tag == "select" and name:
            self._select, self._options = name, []
            self._multiple = "multiple" in a
        elif tag == "option" and self._select is not None:
            self._options.append((a.get("value", ""), "selected" in a))
        elif tag == "textarea" and name:
            self._textarea, self._text = name, []

    def handle_data(self, data: str) -> None:
        if self._textarea is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self.inside = False
        elif tag == "select" and self._select is not None:
            chosen = [v for v, selected in self._options if selected]
            if not chosen and self._options and not self._multiple:
                chosen = [self._options[0][0]]  # a browser posts the first option
            self.fields += [(self._select, v) for v in chosen]
            self._select = None
        elif tag == "textarea" and self._textarea is not None:
            self.fields.append((self._textarea, "".join(self._text)))
            self._textarea = None


def form_fields(html: str, form_id: str) -> list[tuple[str, str]]:
    """What a browser would post for form `form_id` untouched — repeated names (`x[]`) kept."""
    parser = _FormFields(form_id)
    parser.feed(html)
    if not parser.fields:
        raise AssertionError(f"no form #{form_id} with fields on the page")
    return parser.fields


def with_values(fields: list[tuple[str, str]], values: dict[str, str]) -> list[tuple[str, str]]:
    """The defaults with `values` replacing (or adding) single fields."""
    kept = [(k, v) for k, v in fields if k not in values]
    return kept + list(values.items())


def field(fields: list[tuple[str, str]], name: str) -> str:
    return next(v for k, v in fields if k == name)
