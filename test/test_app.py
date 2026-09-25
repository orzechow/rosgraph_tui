"""Headless Textual tests against the fake graph source."""

import copy

import pytest

from rosgraph_tui.app import RosgraphApp
from rosgraph_tui.model import EntityRef, Kind, RawGraph
from rosgraph_tui.source import FakeGraphSource, demo_source
from rosgraph_tui.viewmodel import Column

TALKER = EntityRef(Kind.NODE, "/talker")
LISTENER = EntityRef(Kind.NODE, "/listener")
CHATTER = EntityRef(Kind.TOPIC, "/chatter")
DAEMON = EntityRef(Kind.NODE, "/_ros2cli_daemon_0")
SIZE = (140, 40)


def make_app(source=None, **kwargs):
    return RosgraphApp(source or demo_source(), refresh_rate=0, **kwargs)


async def settle(app, pilot):
    await app.workers.wait_for_complete()
    await pilot.pause()
    await pilot.pause()


def rows(app, column):
    return [r.ref for r in app.column(column).rows]


@pytest.fixture
def demo_raw_without_talker():
    src = demo_source()
    raw = copy.deepcopy(src._raw)
    raw.nodes = [n for n in raw.nodes if n != ("talker", "/")]
    raw.node_pubs.pop("/talker")
    return raw


async def test_initial_view_lists_everything():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        middle = rows(app, Column.MIDDLE)
        assert TALKER in middle and CHATTER in middle
        assert DAEMON not in middle
        assert app.focused_column() == Column.MIDDLE
        assert app.column(Column.MIDDLE).option_list.highlighted == 0
        assert "nodes" in app.sub_title


async def test_typing_filters_and_backspace():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("c", "h", "a", "t")
        await pilot.pause()
        assert app.state.filter_text == "chat"
        assert rows(app, Column.MIDDLE)[0] == CHATTER
        assert "chat" in str(app.column(Column.MIDDLE).query_one(".info").render())
        await pilot.press("backspace")
        assert app.state.filter_text == "cha"
        await pilot.press("slash", "underscore")
        assert app.state.filter_text == "cha/_"


async def test_enter_roots_on_topic():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("c", "h", "a", "t", "t", "e", "r")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.state.root == CHATTER
        assert app.state.filter_text == ""
        assert rows(app, Column.MIDDLE) == [CHATTER]
        assert rows(app, Column.LEFT) == [TALKER]
        assert rows(app, Column.RIGHT) == [LISTENER]
        assert str(app.column(Column.LEFT).query_one(".title").render()).startswith("Publishers")
        assert app.focused_column() == Column.MIDDLE


async def test_arrow_walk_across_columns():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        app.choose(CHATTER)
        await pilot.pause()
        await pilot.press("right")
        assert app.focused_column() == Column.RIGHT
        await pilot.press("right")  # choose the highlighted subscriber
        await pilot.pause()
        assert app.state.root == LISTENER
        assert app.focused_column() == Column.MIDDLE
        # the previous root is pre-highlighted where it now appears
        assert app.column(Column.LEFT).highlighted_ref == CHATTER
        await pilot.press("left")
        assert app.focused_column() == Column.LEFT
        await pilot.press("left")
        await pilot.pause()
        assert app.state.root == CHATTER
        await pilot.press("left")
        await pilot.press("right")
        assert app.focused_column() == Column.MIDDLE


async def test_move_into_empty_column_is_ignored():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        app.column(Column.MIDDLE).highlight(EntityRef(Kind.TOPIC, "/diagnostics"))  # no subscribers
        await pilot.pause()
        await pilot.pause()
        assert rows(app, Column.RIGHT) == []
        await pilot.press("right")
        assert app.focused_column() == Column.MIDDLE
        app.choose(TALKER)  # no subscriptions -> left column empty
        await pilot.pause()
        await pilot.press("left")
        assert app.focused_column() == Column.MIDDLE


async def test_escape_chain_then_exit():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        app.choose(TALKER)
        await pilot.pause()
        await pilot.press("x")
        assert app.state.filter_text == "x"
        await pilot.press("escape")
        assert app.state.filter_text == "" and app.state.root == TALKER
        await pilot.press("escape")
        assert app.state.root is None and app.state.scope is Kind.NODE
        assert all(r.kind is Kind.NODE for r in rows(app, Column.MIDDLE))
        await pilot.press("escape")
        assert app.state.scope is None
        await pilot.press("escape")
        await pilot.pause()
        assert not app.is_running


async def test_toggle_hidden():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert DAEMON in rows(app, Column.MIDDLE)
        assert "hidden shown" in app.sub_title
        await pilot.press("f2")
        await pilot.pause()
        assert DAEMON not in rows(app, Column.MIDDLE)


async def test_include_hidden_flag():
    app = make_app(include_hidden=True)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert DAEMON in rows(app, Column.MIDDLE)


async def test_refresh_preserves_highlight_and_marks_gone_root(demo_raw_without_talker):
    source = demo_source()
    app = make_app(source)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        middle = app.column(Column.MIDDLE)
        middle.highlight(CHATTER)
        first_digest = app.snapshot.digest
        source.set_raw(demo_raw_without_talker)
        app.action_refresh()
        await settle(app, pilot)
        assert app.snapshot.digest != first_digest
        assert TALKER not in rows(app, Column.MIDDLE)
        assert middle.highlighted_ref == CHATTER

        app.choose(TALKER)  # root that no longer exists
        await pilot.pause()
        assert middle.rows[0].style == "gone"
        assert "root gone" in app.sub_title

        source.set_raw(demo_source()._raw)
        app.action_refresh()
        await settle(app, pilot)
        assert middle.rows[0].style == "chosen"
        assert rows(app, Column.RIGHT)


async def test_unchanged_poll_does_not_rerender():
    source = demo_source()
    app = make_app(source)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        middle = app.column(Column.MIDDLE)
        option_list = middle.option_list
        app.action_refresh()
        await settle(app, pilot)
        assert middle.option_list is option_list
        assert middle.set_rows(middle.rows) is False
        assert source.poll_count == 2


async def test_lazy_qos_in_info_line():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        app.choose(TALKER)
        await pilot.pause()
        await pilot.press("right")
        app.column(Column.RIGHT).highlight(CHATTER)
        await settle(app, pilot)
        info = str(app.column(Column.RIGHT).query_one(".info").render())
        assert "std_msgs/msg/String" in info
        assert "reliable / volatile" in info


async def test_poll_error_is_shown_and_survived():
    class Broken(FakeGraphSource):
        def snapshot(self, full=True):
            raise RuntimeError("boom")

    app = make_app(Broken(RawGraph()))
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert "ERROR RuntimeError: boom" in app.sub_title
        assert app.is_running


async def test_ctrl_q_quits():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert not app.is_running


async def test_preview_follows_middle_highlight():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        middle = app.column(Column.MIDDLE)
        middle.highlight(TALKER)
        await pilot.pause()
        await pilot.pause()
        assert app.state.preview == TALKER
        assert CHATTER in rows(app, Column.RIGHT)
        assert str(app.column(Column.RIGHT).query_one(".title").render()).startswith("Publications (3)")
        assert "0 subs / 3 pubs" in str(middle.query_one(".info").render())
        await pilot.press("down")
        await pilot.pause()
        await pilot.pause()
        assert app.state.preview == middle.highlighted_ref != TALKER


async def test_typing_highlights_best_match_and_previews_it():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        middle = app.column(Column.MIDDLE)
        middle.highlight(EntityRef(Kind.NODE, "/planning/planner"))
        await pilot.pause()
        await pilot.press("c", "h", "a", "t")
        await pilot.pause()
        await pilot.pause()
        assert middle.option_list.highlighted == 0
        assert middle.highlighted_ref == CHATTER
        assert rows(app, Column.LEFT) == [TALKER]
        assert rows(app, Column.RIGHT) == [LISTENER]
        info = str(middle.query_one(".info").render())
        assert "/chat" in info and "std_msgs/msg/String" in info
        # clearing the filter keeps the highlight on the current entry
        await pilot.press("escape")
        await pilot.pause()
        await pilot.pause()
        assert app.state.filter_text == ""
        assert middle.highlighted_ref == CHATTER


async def test_walk_into_preview_column_roots():
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        app.column(Column.MIDDLE).highlight(CHATTER)
        await pilot.pause()
        await pilot.pause()
        await pilot.press("right")
        assert app.focused_column() == Column.RIGHT
        await pilot.press("right")
        await pilot.pause()
        assert app.state.root == LISTENER
        assert app.column(Column.LEFT).highlighted_ref == CHATTER
