"""The Textual application: three columns, type-to-filter, live refresh."""

from __future__ import annotations

import signal
import time
from datetime import datetime

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Footer, Header, OptionList

from rosgraph_tui import viewmodel as vm
from rosgraph_tui.model import Endpoint, EntityRef, GraphSnapshot, Kind
from rosgraph_tui.source import GraphSource, SourceError
from rosgraph_tui.viewmodel import Column, ViewState
from rosgraph_tui.widgets import EntityColumn

MAX_INTERVAL = 10.0
POLL_BUDGET = 0.2  # a poll may use at most this fraction of the interval


class RosgraphApp(App[None]):
    CSS_PATH = "app.tcss"
    TITLE = "rosgraph_tui"
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("left", "move_left", "Left", show=False),
        Binding("right", "move_right", "Right", show=False),
        Binding("ctrl+r,f5", "refresh", "Refresh"),
        Binding("ctrl+t,f2", "toggle_hidden", "Hidden"),
        Binding("ctrl+q,ctrl+c", "quit", "Quit", priority=True, key_display="^q"),
    ]

    snapshot: reactive[GraphSnapshot | None] = reactive(None, init=False)
    state: reactive[ViewState] = reactive(ViewState(), init=False)

    def __init__(self, source: GraphSource, include_hidden: bool = False, refresh_rate: float = 1.0) -> None:
        super().__init__()
        self.source = source
        self.base_interval = 1.0 / refresh_rate if refresh_rate > 0 else 0.0
        self._interval = self.base_interval
        self._timer: Timer | None = None
        self._poll_in_flight = False
        self._poll_error = ""
        self._last_poll_at = 0.0
        self._endpoints: dict[tuple[int, str], list[Endpoint]] = {}
        self._render_scheduled = False
        self._last_filter = ""
        self._initial_state = ViewState(include_hidden=include_hidden)

    # --- layout -----------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="columns"):
            yield EntityColumn("left", "Input:")
            yield EntityColumn("middle", "Nodes and Topics:")
            yield EntityColumn("right", "Output:")
        yield Footer()

    @property
    def columns(self) -> list[EntityColumn]:
        return [self.query_one(f"#{name}", EntityColumn) for name in ("left", "middle", "right")]

    def column(self, index: int) -> EntityColumn:
        return self.columns[index]

    def focused_column(self) -> int | None:
        widget = self.focused
        while widget is not None:
            if isinstance(widget, EntityColumn):
                return ("left", "middle", "right").index(widget.id or "")
            widget = widget.parent  # type: ignore[assignment]
        return None

    def focus_column(self, index: int) -> None:
        self.column(index).option_list.focus()

    def on_mount(self) -> None:
        self.state = self._initial_state
        self.focus_column(Column.MIDDLE)
        self._install_signal_handlers()
        self._render()
        self._start_poll(full=True)
        self._arm_timer(self.base_interval)

    def _install_signal_handlers(self) -> None:
        try:
            import asyncio

            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self.exit)
        except (NotImplementedError, RuntimeError):  # pragma: no cover - platform dependent
            pass

    # --- polling ----------------------------------------------------------

    def _arm_timer(self, interval: float) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        self._interval = interval
        if interval > 0:
            self._timer = self.set_interval(interval, self._tick, name="poll")

    def _tick(self) -> None:
        self._start_poll(full=False)

    def action_refresh(self) -> None:
        self._start_poll(full=True)

    def _start_poll(self, full: bool) -> None:
        if self._poll_in_flight:
            return
        self._poll_in_flight = True
        self._poll(full)

    @work(thread=True, group="poll", exit_on_error=False)
    def _poll(self, full: bool) -> None:
        try:
            snapshot = self.source.snapshot(full=full)
        except SourceError as exc:
            self.call_from_thread(self._apply_poll_error, str(exc))
        except Exception as exc:  # noqa: BLE001 - keep the UI alive, show the error
            self.call_from_thread(self._apply_poll_error, f"{type(exc).__name__}: {exc}")
        else:
            self.call_from_thread(self._apply_snapshot, snapshot)

    def _apply_poll_error(self, message: str) -> None:
        self._poll_in_flight = False
        self._poll_error = message
        self._update_subtitle()

    def _apply_snapshot(self, snapshot: GraphSnapshot) -> None:
        self._poll_in_flight = False
        self._poll_error = ""
        self._last_poll_at = time.time()
        current = self.snapshot
        if current is not None and current.digest != snapshot.digest:
            self._endpoints.clear()
        if current is None or current.digest != snapshot.digest:
            self.snapshot = snapshot  # triggers a render
        else:
            self._update_subtitle()
        self._adapt_interval(snapshot.poll_ms / 1000.0)

    def _adapt_interval(self, poll_seconds: float) -> None:
        if self.base_interval <= 0:
            return
        desired = min(MAX_INTERVAL, max(self.base_interval, poll_seconds / POLL_BUDGET))
        if abs(desired - self._interval) > 0.2 * self._interval:
            self._arm_timer(desired)

    # --- lazy QoS ---------------------------------------------------------

    def _endpoints_for(self, ref: EntityRef | None) -> list[Endpoint] | None:
        if ref is None or ref.kind is not Kind.TOPIC or self.snapshot is None:
            return None
        key = (self.snapshot.digest, ref.name)
        endpoints = self._endpoints.get(key)
        if endpoints is None:
            self._fetch_endpoints(key)
        return endpoints

    @work(thread=True, group="qos", exclusive=True, exit_on_error=False)
    def _fetch_endpoints(self, key: tuple[int, str]) -> None:
        try:
            endpoints = self.source.topic_endpoints(key[1])
        except Exception:  # noqa: BLE001
            endpoints = []
        self.call_from_thread(self._store_endpoints, key, endpoints)

    def _store_endpoints(self, key: tuple[int, str], endpoints: list[Endpoint]) -> None:
        self._endpoints[key] = endpoints
        self._update_infos()

    # --- rendering --------------------------------------------------------

    def watch_snapshot(self, _old: object, _new: object) -> None:
        self._schedule_render()

    def watch_state(self, _old: object, _new: object) -> None:
        self._schedule_render()

    def _schedule_render(self) -> None:
        """Coalesce bursts (fast typing, snapshot + state) into one render."""
        if self._render_scheduled:
            return
        self._render_scheduled = True
        self.call_after_refresh(self._render)

    def _render(self) -> None:
        self._render_scheduled = False
        if not self.is_mounted:
            return
        view = vm.derive_view(self.snapshot, self.state)
        filter_changed = self.state.filter_text != self._last_filter
        self._last_filter = self.state.filter_text
        left, middle, right = self.columns
        for column, model in zip((left, middle, right), (view.left, view.middle, view.right), strict=True):
            column.set_title(model.title)
            # a new non-empty filter puts the highlight on the best match
            keep = not (column is middle and filter_changed and self.state.filter_text)
            column.set_rows(model.rows, keep_highlight=keep)
        self._sync_preview()
        self._update_infos(view)
        self._update_subtitle(view.status)

    def _sync_preview(self) -> None:
        """Keep ``state.preview`` equal to the middle highlight while browsing."""
        if self.state.root is not None:
            return
        ref = self.column(Column.MIDDLE).highlighted_ref
        new_state = vm.set_preview(self.state, ref)
        if new_state is not self.state:
            self.state = new_state  # schedules one more (cheap, memoised) render

    def _update_infos(self, view: vm.ViewModel | None = None) -> None:
        if view is None:
            view = vm.derive_view(self.snapshot, self.state)
        snapshot = self.snapshot.visible(self.state.include_hidden) if self.snapshot else None
        left, middle, right = self.columns
        for column in (left, right):
            ref = column.highlighted_ref
            entity = snapshot.get(ref) if snapshot and ref else None
            column.set_info(vm.info_line(entity, self._endpoints_for(ref)))
        focus_ref = self.state.root if self.state.root is not None else middle.highlighted_ref
        entity = snapshot.get(focus_ref) if snapshot and focus_ref else None
        lines = []
        if self.state.filter_text:
            lines.append(f"/{self.state.filter_text}▏")
        lines.append(vm.info_line(entity, self._endpoints_for(focus_ref)) if entity else "type to filter")
        middle.set_info("\n".join(lines))

    def _update_subtitle(self, status: str = "") -> None:
        parts = [self.source.describe()]
        snapshot = self.snapshot
        if snapshot is not None and snapshot.entities:
            parts.append(f"{snapshot.count(Kind.NODE)} nodes")
            parts.append(f"{snapshot.count(Kind.TOPIC)} topics")
            parts.append("hidden shown" if self.state.include_hidden else "hidden off")
            parts.append(f"poll {snapshot.poll_ms:.0f} ms")
            if self._interval > 0:
                parts.append(f"every {self._interval:.1f} s")
            if self._last_poll_at:
                parts.append(datetime.fromtimestamp(self._last_poll_at).strftime("%H:%M:%S"))
        if status:
            parts.append(status)
        if self._poll_error:
            parts.append(f"ERROR {self._poll_error}")
        self.sub_title = " · ".join(parts)

    # --- input ------------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        if event.key == "backspace":
            if self.state.filter_text:
                self.state = vm.backspace(self.state)
            event.stop()
            return
        if event.character is None:
            return
        new_state = vm.type_char(self.state, event.character)
        if new_state is None:
            return
        self.state = new_state
        if self.state.root is None:
            self.focus_column(Column.MIDDLE)
        event.stop()
        event.prevent_default()

    @on(OptionList.OptionSelected)
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        column = event.option_list.parent
        if isinstance(column, EntityColumn):
            ref = column.ref_at(event.option_index)
            if ref is not None:
                self.choose(ref)

    @on(OptionList.OptionHighlighted)
    def _on_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        column = event.option_list.parent
        if isinstance(column, EntityColumn) and column.id == "middle" and self.state.root is None:
            self._sync_preview()
        self._update_infos()

    def on_descendant_focus(self, _event: events.DescendantFocus) -> None:
        self._update_infos()

    def choose(self, ref: EntityRef) -> None:
        previous = self.state.root
        self.state = vm.choose(self.state, ref)
        self._render()  # synchronous so the highlight below sees the new rows
        self.focus_column(Column.MIDDLE)
        if previous is not None:
            for index in (Column.LEFT, Column.RIGHT):
                if self.column(index).highlight(previous):
                    break
        self._update_infos()

    def action_back(self) -> None:
        new_state = vm.escape(self.state)
        if new_state is None:
            self.exit()
            return
        self.state = new_state
        self.focus_column(Column.MIDDLE)

    def action_move_left(self) -> None:
        column = self.focused_column()
        if column == Column.LEFT:
            ref = self.column(Column.LEFT).highlighted_ref
            if ref is not None:
                self.choose(ref)
        elif column == Column.RIGHT:
            self.focus_column(Column.MIDDLE)
        elif column == Column.MIDDLE and self.column(Column.LEFT).rows:
            self.focus_column(Column.LEFT)

    def action_move_right(self) -> None:
        column = self.focused_column()
        if column == Column.RIGHT:
            ref = self.column(Column.RIGHT).highlighted_ref
            if ref is not None:
                self.choose(ref)
        elif column == Column.LEFT:
            self.focus_column(Column.MIDDLE)
        elif column == Column.MIDDLE and self.column(Column.RIGHT).rows:
            self.focus_column(Column.RIGHT)

    def action_toggle_hidden(self) -> None:
        self.state = vm.toggle_hidden(self.state)
