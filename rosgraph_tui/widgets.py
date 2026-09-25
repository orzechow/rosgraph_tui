"""Textual widgets: one column = title, virtualised list, info line."""

from __future__ import annotations

from collections.abc import Sequence

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from rosgraph_tui.model import EntityRef, Kind
from rosgraph_tui.viewmodel import Row

_KIND_COLOR = {Kind.NODE: "", Kind.TOPIC: "cyan"}
_STYLE_MOD = {
    "node": "",
    "topic": "",
    "chosen": "bold",
    "unconnected": "red",
    "hidden": "dim",
    "gone": "red strike",
}


def row_text(row: Row) -> Text:
    color = _KIND_COLOR[row.ref.kind]
    mod = _STYLE_MOD.get(row.style, "")
    if row.style in ("unconnected", "gone"):
        color = ""  # red wins over the kind colour
    style = " ".join(part for part in (color, mod) if part)
    return Text(row.label, style=style, no_wrap=True, overflow="ellipsis")


class EntityColumn(Vertical):
    """A titled list of entities with an info line underneath."""

    DEFAULT_CLASSES = "column"

    def __init__(self, column_id: str, title: str) -> None:
        super().__init__(id=column_id)
        self._title = title
        self._rows: tuple[Row, ...] = ()
        self._row_key: tuple | None = None

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="title")
        yield OptionList(id=f"{self.id}-list")
        yield Static("", classes="info")

    # --- accessors ---------------------------------------------------------

    @property
    def option_list(self) -> OptionList:
        return self.query_one(OptionList)

    @property
    def rows(self) -> tuple[Row, ...]:
        return self._rows

    @property
    def highlighted_ref(self) -> EntityRef | None:
        index = self.option_list.highlighted
        if index is None or index >= len(self._rows):
            return None
        return self._rows[index].ref

    def ref_at(self, index: int | None) -> EntityRef | None:
        if index is None or index < 0 or index >= len(self._rows):
            return None
        return self._rows[index].ref

    def index_of(self, ref: EntityRef | None) -> int | None:
        if ref is None:
            return None
        for i, row in enumerate(self._rows):
            if row.ref == ref:
                return i
        return None

    # --- mutators ----------------------------------------------------------

    def set_title(self, title: str) -> None:
        if title != self._title:
            self._title = title
            self.query_one(".title", Label).update(title)

    def set_info(self, text: str) -> None:
        self.query_one(".info", Static).update(text)

    def highlight(self, ref: EntityRef | None) -> bool:
        index = self.index_of(ref)
        if index is None:
            return False
        self.option_list.highlighted = index
        return True

    def set_rows(self, rows: Sequence[Row]) -> bool:
        """Replace the rows, keeping the highlight on the same entity.

        Returns False (and does nothing) when the rows are unchanged, so a
        1 Hz refresh of an unchanged graph costs no rendering at all.
        """
        rows = tuple(rows)
        key = tuple((r.ref, r.style) for r in rows)
        if key == self._row_key:
            return False

        option_list = self.option_list
        previous_ref = self.highlighted_ref
        previous_index = option_list.highlighted

        self._rows = rows
        self._row_key = key
        option_list.clear_options()
        if rows:
            option_list.add_options([Option(row_text(row)) for row in rows])
            index = self.index_of(previous_ref)
            if index is None:
                index = 0 if previous_index is None else max(0, min(previous_index, len(rows) - 1))
            option_list.highlighted = index
        return True
