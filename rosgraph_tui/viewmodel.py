"""Pure view logic: state transitions and derivation of the three columns.

Nothing here touches Textual or ROS, so every navigation rule is unit-tested
without a terminal.  ``derive_view`` is memoised; with an unchanged snapshot
and state it costs a dict lookup.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import lru_cache

from rosgraph_tui.model import Endpoint, Entity, EntityRef, GraphSnapshot, Kind
from rosgraph_tui.search import fuzzy_filter, fuzzy_rank

FILTER_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_/.-")


@dataclass(frozen=True)
class ViewState:
    root: EntityRef | None = None  # chosen entity; the view is rooted on it
    scope: Kind | None = None  # restrict the un-rooted middle column to one kind
    filter_text: str = ""
    include_hidden: bool = False
    preview: EntityRef | None = None  # highlighted middle entry while not rooted


@dataclass(frozen=True)
class Row:
    ref: EntityRef
    style: str  # node | topic | chosen | unconnected | hidden | gone
    label: str


@dataclass(frozen=True)
class ColumnModel:
    title: str
    rows: tuple[Row, ...] = ()
    info: str = ""


@dataclass(frozen=True)
class ViewModel:
    left: ColumnModel
    middle: ColumnModel
    right: ColumnModel
    status: str = ""


class Column:
    LEFT = 0
    MIDDLE = 1
    RIGHT = 2


# --- state transitions -------------------------------------------------------


def choose(state: ViewState, ref: EntityRef) -> ViewState:
    """Re-root the view on ``ref`` and clear the filter."""
    return replace(state, root=ref, scope=ref.kind, filter_text="")


def escape(state: ViewState) -> ViewState | None:
    """One step back per press; ``None`` means: nothing left, exit."""
    if state.filter_text:
        return replace(state, filter_text="")
    if state.root is not None:
        return replace(state, root=None)
    if state.scope is not None:
        return replace(state, scope=None)
    return None


def type_char(state: ViewState, char: str) -> ViewState | None:
    if len(char) == 1 and char in FILTER_CHARS:
        return replace(state, filter_text=state.filter_text + char)
    return None


def backspace(state: ViewState) -> ViewState:
    return replace(state, filter_text=state.filter_text[:-1])


def toggle_hidden(state: ViewState) -> ViewState:
    return replace(state, include_hidden=not state.include_hidden)


def set_preview(state: ViewState, ref: EntityRef | None) -> ViewState:
    return state if state.preview == ref else replace(state, preview=ref)


# --- derivation --------------------------------------------------------------


def _style(entity: Entity, column: int, chosen: EntityRef | None) -> str:
    if entity.ref == chosen:
        return "chosen"
    if entity.kind is Kind.TOPIC:
        if column == Column.LEFT and not entity.inputs:
            return "unconnected"  # a subscribed topic nobody publishes
        if column == Column.RIGHT and not entity.outputs:
            return "unconnected"  # a published topic nobody reads
    if column == Column.MIDDLE and entity.unconnected:
        return "unconnected"
    if entity.hidden:
        return "hidden"
    return entity.kind.value


def _rows(
    snapshot: GraphSnapshot, refs: Sequence[EntityRef], column: int, chosen: EntityRef | None
) -> tuple[Row, ...]:
    rows = []
    for ref in refs:
        entity = snapshot.get(ref)
        if entity is None:
            continue
        rows.append(Row(ref, _style(entity, column, chosen), ref.label))
    return tuple(rows)


@lru_cache(maxsize=16)
def _middle_refs(snapshot: GraphSnapshot, kind: Kind | None, query: str) -> tuple[EntityRef, ...]:
    """The fuzzy pass over the whole graph; cached so preview changes do not repeat it."""
    return tuple(_filtered(snapshot, kind, query))


@lru_cache(maxsize=16)
def _middle_column(snapshot: GraphSnapshot, kind: Kind | None, query: str) -> ColumnModel:
    """The un-rooted middle column; cached so a preview change costs no row building."""
    rows = _rows(snapshot, _middle_refs(snapshot, kind, query), Column.MIDDLE, None)
    return ColumnModel(_scope_title(snapshot, kind) + ":", rows, info=query)


def _filtered(snapshot: GraphSnapshot, kind: Kind | None, query: str) -> list[EntityRef]:
    if kind is not None:
        return [EntityRef(kind, n) for n in fuzzy_filter(snapshot.names(kind), query)]
    if not query:
        return [EntityRef(k, n) for k in Kind for n in snapshot.names(k)]
    # both kinds: rank everything by score, then kind, then name
    ranked = []
    for order, k in enumerate(Kind):
        ranked.extend((-score, order, n, k) for n, score in fuzzy_rank(snapshot.names(k), query))
    ranked.sort()
    return [EntityRef(k, n) for _s, _o, n, k in ranked]


def _filter_refs(refs: Sequence[EntityRef], query: str) -> list[EntityRef]:
    if not query:
        return list(refs)
    by_name = {r.name: r for r in refs}
    return [by_name[n] for n in fuzzy_filter(sorted(by_name), query)]


def _scope_title(snapshot: GraphSnapshot, scope: Kind | None) -> str:
    if scope is None:
        return f"Nodes and Topics ({snapshot.count(Kind.NODE)} / {snapshot.count(Kind.TOPIC)})"
    return f"{scope.title}s ({snapshot.count(scope)})"


@lru_cache(maxsize=16)
def derive_view(snapshot: GraphSnapshot | None, state: ViewState) -> ViewModel:
    if snapshot is None or not snapshot.entities:
        empty = ColumnModel("Input:")
        middle = ColumnModel("Nodes and Topics:")
        return ViewModel(empty, middle, ColumnModel("Output:"), status="Discovering…")

    vis = snapshot.visible(state.include_hidden)
    query = state.filter_text

    if state.root is None:
        middle = _middle_column(vis, state.scope, query)
        left, right = _side_columns(vis, state.preview, "")
        return ViewModel(left, middle, right)

    root = state.root
    entity = vis.get(root)
    if entity is None:
        gone = Row(root, "gone", root.label)
        middle = ColumnModel(f"{root.kind.title} (gone):", (gone,), info=query)
        return ViewModel(ColumnModel("Input:"), middle, ColumnModel("Output:"), status="root gone")

    left, right = _side_columns(vis, root, query)
    middle = ColumnModel(f"{root.kind.title}:", _rows(vis, [root], Column.MIDDLE, root), info=query)
    return ViewModel(left, middle, right)


def _side_columns(vis: GraphSnapshot, ref: EntityRef | None, query: str) -> tuple[ColumnModel, ColumnModel]:
    """Inputs and outputs of ``ref`` (the root, or the previewed entry)."""
    entity = vis.get(ref) if ref is not None else None
    if entity is None:
        return ColumnModel("Input:"), ColumnModel("Output:")
    if ref.kind is Kind.NODE:
        left_title, right_title = "Subscriptions", "Publications"
    else:
        left_title, right_title = "Publishers", "Subscribers"
    inputs = _filter_refs(entity.inputs, query)
    outputs = _filter_refs(entity.outputs, query)
    left = ColumnModel(f"{left_title} ({len(inputs)}):", _rows(vis, inputs, Column.LEFT, None))
    right = ColumnModel(f"{right_title} ({len(outputs)}):", _rows(vis, outputs, Column.RIGHT, None))
    return left, right


# --- info line ---------------------------------------------------------------


def info_line(entity: Entity | None, endpoints: Sequence[Endpoint] | None = None) -> str:
    """Footer text for a highlighted entity."""
    if entity is None:
        return ""
    if entity.kind is Kind.NODE:
        parts = [f"{len(entity.inputs)} subs / {len(entity.outputs)} pubs"]
        if entity.instances > 1:
            parts.append(f"{entity.instances} instances")
        if entity.hidden:
            parts.append("hidden")
        return " · ".join(parts)
    types = ", ".join(entity.types) or "unknown type"
    parts = [f"Type: {types}", f"{len(entity.inputs)} pubs / {len(entity.outputs)} subs"]
    if endpoints:
        qos = sorted({str(e.qos) for e in endpoints if e.qos is not None})
        if qos:
            parts.append("QoS: " + " | ".join(qos))
    if entity.hidden:
        parts.append("hidden")
    return " · ".join(parts)
