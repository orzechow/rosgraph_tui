"""Performance budgets on a synthetic Autoware-scale graph (300 nodes, 2000 topics, 8000 edges).

Budgets are generous multiples of what a laptop achieves so CI noise does
not flake them; they exist to catch accidental O(n^2) regressions.
"""

import time

import pytest

from rosgraph_tui.app import RosgraphApp
from rosgraph_tui.model import EntityRef, Kind, build_snapshot
from rosgraph_tui.source import FakeGraphSource
from rosgraph_tui.viewmodel import Column, ViewState, choose, derive_view

from .big_graph import make_big_raw

pytestmark = pytest.mark.perf


def timed(fn, repeat=3):
    best = float("inf")
    result = None
    for _ in range(repeat):
        start = time.perf_counter()
        result = fn()
        best = min(best, time.perf_counter() - start)
    return result, best * 1000.0


@pytest.fixture(scope="module")
def big_raw():
    return make_big_raw()


@pytest.fixture(scope="module")
def big_snapshot(big_raw):
    return build_snapshot(big_raw)


def test_build_snapshot_budget(big_raw):
    snap, ms = timed(lambda: build_snapshot(big_raw))
    assert snap.count(Kind.NODE) == 301
    assert snap.count(Kind.TOPIC) == 2001
    assert ms < 250, f"build_snapshot took {ms:.1f} ms"


def test_digest_budget(big_raw):
    _, ms = timed(big_raw.digest)
    assert ms < 100, f"digest took {ms:.1f} ms"


def test_derive_view_budget(big_snapshot):
    derive_view.cache_clear()
    _, ms_all = timed(lambda: derive_view(big_snapshot, ViewState()))
    derive_view.cache_clear()
    _, ms_filter = timed(lambda: derive_view(big_snapshot, ViewState(filter_text="lidar/topic_1")))
    root = EntityRef(Kind.NODE, big_snapshot.names(Kind.NODE)[10])
    derive_view.cache_clear()
    _, ms_root = timed(lambda: derive_view(big_snapshot, choose(ViewState(), root)))
    assert ms_all < 100, f"unfiltered view took {ms_all:.1f} ms"
    assert ms_filter < 150, f"filtered view took {ms_filter:.1f} ms"
    assert ms_root < 50, f"rooted view took {ms_root:.1f} ms"
    # memoised: second call is a cache hit
    _, ms_cached = timed(lambda: derive_view(big_snapshot, ViewState()))
    assert ms_cached < 1


def test_visible_view_budget(big_snapshot):
    _, ms = timed(lambda: build_snapshot(make_big_raw()).visible(False))
    assert ms < 400, f"visible() on a fresh snapshot took {ms:.1f} ms"


async def test_render_budget(big_raw):
    source = FakeGraphSource(big_raw)
    app = RosgraphApp(source, refresh_rate=0)
    async with app.run_test(size=(160, 50)) as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.pause()
        middle = app.column(Column.MIDDLE)
        assert len(middle.rows) == 2300  # hidden ones excluded

        # an unchanged poll must not rebuild anything
        start = time.perf_counter()
        app.action_refresh()
        await app.workers.wait_for_complete()
        await pilot.pause()
        unchanged_ms = (time.perf_counter() - start) * 1000
        assert source.poll_count == 2
        assert unchanged_ms < 200, f"unchanged refresh cost {unchanged_ms:.1f} ms"

        # typing a filter re-renders the middle column (2302 -> a few hundred rows)
        start = time.perf_counter()
        await pilot.press("l", "i", "d", "a", "r")
        await pilot.pause()
        typing_ms = (time.perf_counter() - start) * 1000
        assert 0 < len(middle.rows) < 2300
        assert typing_ms < 1500, f"typing 5 chars cost {typing_ms:.1f} ms"

        # moving the highlight (preview) must not rebuild the 2300-row middle column:
        # our own render work per step stays in the low milliseconds ...
        await pilot.press("escape")
        await pilot.pause()
        from rosgraph_tui import viewmodel as vm

        worst = 0.0
        for row in middle.rows[1:6]:
            app.state = vm.set_preview(app.state, row.ref)
            start = time.perf_counter()
            app._render()
            worst = max(worst, (time.perf_counter() - start) * 1000)
        assert middle.set_rows(middle.rows) is False
        assert worst < 50, f"a preview render cost {worst:.1f} ms"
        # ... and the whole key press, including Textual's list handling, stays interactive
        start = time.perf_counter()
        for _ in range(5):
            await pilot.press("down")
        await pilot.pause()
        preview_ms = (time.perf_counter() - start) * 1000
        assert app.state.preview == middle.highlighted_ref
        assert preview_ms < 2500, f"5 preview key presses cost {preview_ms:.1f} ms"

        # rooting on a busy node
        node = max(source.snapshot().of_kind(Kind.NODE), key=lambda e: len(e.outputs))
        start = time.perf_counter()
        app.choose(node.ref)
        await pilot.pause()
        root_ms = (time.perf_counter() - start) * 1000
        assert root_ms < 600, f"choose() cost {root_ms:.1f} ms"  # mostly OptionList clearing 2300 rows
