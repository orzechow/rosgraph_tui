# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Textual (TUI) app that lets you fuzzy-search and walk a ROS 2 graph (nodes ⇄ topics), built for
very large graphs. Branch `ros2_port` is the ROS 2 rewrite; `main` still holds the old ROS 1 / urwid
code until PR 2 is merged.

## Commands

```bash
uv sync                                   # dev env (.venv) from uv.lock; rclpy is NOT a pip dep
uv run pytest                             # everything that runs without ROS (~65 tests, ~15 s)
uv run pytest test/test_viewmodel.py -k preview   # one file / one test
uv run pytest -m "not perf"               # skip the timing budgets
uv run ruff check rosgraph_tui test scripts
uv run rosgraph_tui --demo                # run against the bundled fixture, no ROS needed
uv run rosgraph_tui --fixture path.json   # any RawGraph-shaped JSON (format: rosgraph_tui/fixtures/demo.json)
uv sync --group media && uv run python scripts/make_media.py   # regenerate docs/screenshot.png + docs/demo.gif
```

With a sourced ROS 2 environment (rclpy on `PYTHONPATH`): `uv run pytest -m ros` runs
`test/ros/` against a real talker/listener subprocess, and `scripts/bench_poll.py` times polls.
Locally there is no ROS; CI runs those inside `ros:jazzy-ros-core` (see `.github/workflows/ci.yml`).
The same can be done here with Docker: build an image from `ros:jazzy-ros-core` with pip + a
`--system-site-packages` venv, mount the repo, `source /opt/ros/jazzy/setup.bash`, `pip install -e .`,
`pytest`. `packages.ros.org` is blocked in this sandbox, so install colcon via pip, not apt.

`pyproject.toml` blocks the ROS-shipped pytest plugins (`-p no:launch_testing -p no:launch_ros`);
they crash pytest ≥ 9. Keep that if you touch `addopts`.

## Architecture

Data flows one way: `GraphSource.snapshot()` → `GraphSnapshot` → `derive_view(snapshot, ViewState)`
→ `ViewModel` → widgets. Only `app.py` has side effects.

- `model.py` — pure, ROS-free. `RawGraph` is the ROS-shaped poll result (nodes as `(name, namespace)`,
  topics as `(fqn, [types])`, per-node pub/sub lists). `build_snapshot()` indexes it once into an
  immutable `GraphSnapshot` (entities keyed by `EntityRef(kind, name)`, precomputed `inputs`/`outputs`
  tuples, `hidden` per ros2cli's `_` rule, duplicate node `instances`). `GraphSnapshot` has `eq=False`
  so it hashes by identity and can key `lru_cache`s; `visible(include_hidden)` and `names(kind)` are
  cached properties. `RawGraph.digest()` is the content hash the app uses to skip unchanged polls.
- `source.py` — `GraphSource` ABC (`snapshot(full)`, `topic_endpoints(topic)`, `close()`, `describe()`)
  plus `FakeGraphSource` (in-memory / JSON fixtures, `set_raw()` simulates live changes) and
  `demo_source()`. All tests and `--demo` use this.
- `rclpy_source.py` — the only module importing rclpy (lazily; `SourceError` with a hint if missing).
  Owns its own `rclpy.Context` so it coexists with code that already called `rclpy.init`. A poll is
  two calls per *node* (`get_publisher/subscriber_names_and_types_by_node`), never per topic; QoS comes
  from `topic_endpoints()` only for the topic under the cursor. `snapshot(full=False)` compares the
  node/topic lists with the last poll and returns the previous snapshot when unchanged, except every
  `full_every`-th call. No executor is spun. Keep this cheap: Autoware-scale graphs are the target.
- `search.py` — rapidfuzz `partial_ratio`, case-insensitive, cutoff strictly > 50.
- `viewmodel.py` — `ViewState` (frozen: `root`, `scope`, `filter_text`, `include_hidden`, `preview`)
  and the only transitions: `choose`, `escape` (one step per press: filter → root → scope → exit),
  `type_char`, `backspace`, `toggle_hidden`, `set_preview`. `derive_view` is `lru_cache`d on
  `(snapshot, state)`; the un-rooted middle column is cached separately (`_middle_column`) so a
  preview change (highlight moving) costs ~3 ms on 2000 topics. `preview` fills the side columns while
  not rooted; the typed filter narrows the middle list (and the side columns only when rooted).
- `app.py` — `RosgraphApp`. Two reactives (`snapshot`, `state`); any change schedules one coalesced
  `_render()` via `call_after_refresh`. Polling: `set_interval` → thread worker → `source.snapshot()` →
  `call_from_thread(_apply_snapshot)`; same digest ⇒ no reactive change ⇒ no render. The interval
  adapts so a poll never exceeds ~20 % of it. Key handling: printable chars/backspace in `on_key`
  (no `Input` widget, so arrows stay free), everything else via `BINDINGS`. `_sync_preview()` keeps
  `state.preview` equal to the middle highlight. A filter change re-renders the middle column with
  `keep_highlight=False` so the best match is highlighted.
- `widgets.py` — `EntityColumn` = title `Label` + virtualised `OptionList` + info `Static`.
  `set_rows()` returns early when `(ref, style)` per row is unchanged, otherwise rebuilds and restores
  the highlight by ref. Never touches focus. Use `.title` / `.info` class selectors (`Label` is a
  `Static`, so `query_one(Static)` would hit the title).
- `cli.py` — argparse; everything after `--ros-args` is passed whole to `rclpy.init`. `--demo` must
  not import rclpy (tested in a subprocess).

## Tests

`test/` (ROS convention, not `tests/`). `conftest.py` provides `demo`, `demo_snapshot`, `tiny_raw`.
`test_app.py` drives the app headlessly with `App.run_test()` + Pilot against the fake source with
`refresh_rate=0`; after `action_refresh()` await `app.workers.wait_for_complete()` then `pilot.pause()`
twice. `test_perf.py` (marker `perf`) enforces budgets on `test/big_graph.py` (300 nodes / 2000 topics /
8000 edges); budgets are loose multiples, keep them that way — pilot key presses cost ~150 ms each in
the harness regardless of our code. `test/ros/` (marker `ros`, `importorskip("rclpy")`) is skipped
without ROS.

## Packaging

Metadata lives in `pyproject.toml` (PEP 621, needed for uv). `setup.py` stays for colcon/ament_python:
it only adds the ament `data_files` and a `Distribution` subclass that turns `requires-python` back into
a string, because colcon-python-setup-py `literal_eval`s a repr of the distribution and chokes on
`SpecifierSet`. Do not move `requires-python` out of pyproject and do not put metadata back in
`setup.py`. `setup.cfg` redirects scripts to `lib/rosgraph_tui` for `ros2 run`. On Humble, colcon
needs `setuptools>=61` in the venv. rclpy is only in `package.xml`, never in pip dependencies.

## Conventions

Python ≥ 3.10 (Humble): no `StrEnum`, `Self`, `tomllib`. ruff line length 110, rules E/F/W/I/UP/B.
Ubuntu's system Python is externally managed: all install instructions use a venv; in zsh quote
extras (`'.[dev]'`). README install URLs point at `@ros2_port` until the PR is merged into `main`.
