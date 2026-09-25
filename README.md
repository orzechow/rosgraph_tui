# rosgraph_tui

*rosgraph_tui* is a [terminal user interface (TUI)](https://en.wikipedia.org/wiki/Text-based_user_interface)
that lets you explore and debug your **ROS 2** graph interactively.

It is meant as a substitute for `rqt_graph`, which is handy for small projects but
virtually unusable with graphs of hundreds of nodes and thousands of topics
(think Autoware). *rosgraph_tui* lets you fuzzy-search nodes and topics, inspect
them and walk through the graph node → topic → node with the arrow keys, and it
keeps up with a live, changing graph.

```
 Publishers (1):            Topic:                        Subscribers (1):
 N /camera/driver           T /camera/image_raw           N /camera/rectify

 0 subs / 2 pubs            Type: sensor_msgs/msg/Image   2 subs / 1 pubs
                            QoS: best_effort / volatile
```

Powered by [Textual](https://github.com/Textualize/textual) for the UI,
[rapidfuzz](https://github.com/rapidfuzz/RapidFuzz) for fuzzy search and
[rclpy](https://github.com/ros2/rclpy) for graph introspection.

## Features

- One list of all nodes and topics; type to fuzzy-filter it, the best match is highlighted.
- While browsing, the highlighted entry's inputs and outputs are previewed in the side columns.
- Choose an entry to root the view on it: inputs on the left (subscriptions of a
  node, publishers of a topic), outputs on the right.
- Arrow past the edge of a side column to re-root on that entry and keep walking.
- Topic type and, for the topic you are looking at, the QoS of every endpoint.
- Unconnected topics (no publisher or no subscriber) are highlighted in red.
- Live refresh: nodes appearing and vanishing are picked up automatically, the
  highlight stays where it was, and a rooted entry that disappears is shown as
  *gone* until it comes back.
- Hidden names (any `_`-prefixed token, e.g. `/_ros2cli_daemon_0`) are hidden like
  in `ros2 node list`; toggle them with `Ctrl+T`.
- Built for big graphs: two rclpy calls per node per poll (never per topic), cheap
  change detection, adaptive poll interval, memoised view derivation and a
  virtualised list that is only rebuilt when something changed.
- Works without ROS 2 too (`--demo`, `--fixture`), which is how it is tested.

## Installation

Supported: ROS 2 Humble and newer (Python ≥ 3.10). The commands below work in
zsh and bash. Ubuntu's system Python is *externally managed* (PEP 668), so
everything is installed into a virtual environment; you need

```zsh
sudo apt install python3-venv python3-pip git
```

**From git, inside a sourced ROS 2 environment** (rclpy comes from ROS,
everything else from PyPI). Not on PyPI yet.

```zsh
source /opt/ros/lyrical/setup.zsh          # or jazzy, humble, ...; setup.bash in bash
python3 -m venv --system-site-packages ~/.venvs/rosgraph_tui
~/.venvs/rosgraph_tui/bin/pip install 'git+https://github.com/orzechow/rosgraph_tui@ros2_port'
~/.venvs/rosgraph_tui/bin/rosgraph_tui
```

The ROS setup script puts rclpy on `PYTHONPATH`, so the tool finds it from the
venv as long as ROS is sourced in the shell you run it from. Replace
`@ros2_port` with `@main` once the port is merged. Add
`~/.venvs/rosgraph_tui/bin` to your `PATH` or alias the binary if you like.

**As a colcon package:**

```zsh
cd ~/ros2_ws/src && git clone -b ros2_port https://github.com/orzechow/rosgraph_tui
python3 -m venv --system-site-packages ~/.venvs/rosgraph_tui
~/.venvs/rosgraph_tui/bin/pip install textual rapidfuzz   # no recent enough rosdep keys
source ~/.venvs/rosgraph_tui/bin/activate
cd ~/ros2_ws && colcon build --packages-select rosgraph_tui && source install/setup.zsh
ros2 run rosgraph_tui rosgraph_tui
```

(`pip install --break-system-packages textual rapidfuzz` works too if you
prefer not to keep a venv activated. On Humble, add `'setuptools>=61'` to the
`pip install`, because the metadata lives in `pyproject.toml` and Ubuntu 22.04's
setuptools 59 cannot read it.)

**Without ROS 2**, to try it out:

```zsh
python3 -m venv ~/.venvs/rosgraph_tui
~/.venvs/rosgraph_tui/bin/pip install 'git+https://github.com/orzechow/rosgraph_tui@ros2_port'
~/.venvs/rosgraph_tui/bin/rosgraph_tui --demo
```

## Usage

| Key | Action |
| --- | --- |
| letters, digits, `_ / . -` | filter the list (fuzzy, case-insensitive) |
| `Backspace` | delete the last filter character |
| `↑` `↓` | move the highlight; the highlighted entry's inputs and outputs are previewed left and right |
| `Enter` / double-click | root the view on the highlighted entry |
| `←` `→` | move between the columns; press again at the outer edge to root on that entry |
| `Esc` | one step back: clear filter → un-root → show nodes and topics → quit |
| `Ctrl+T` / `F2` | show or hide hidden names |
| `Ctrl+R` / `F5` | refresh now |
| `Ctrl+Q` / `Ctrl+C` | quit |

Command line:

```
rosgraph_tui [--include-hidden] [--refresh-rate HZ] [--full-poll-every N]
             [--demo | --fixture PATH] [--ros-args ...]
```

- `--refresh-rate` (default 1 Hz, `0` = manual only) is an upper bound; if a poll
  takes long the interval is stretched so polling never uses more than ~20 % of
  the time.
- `--full-poll-every N` (default 5): between full polls, a poll only re-reads
  node connections when the node or topic list changed.
- Everything after `--ros-args` goes to rclpy, e.g. `--ros-args -r __node:=my_tui`.

The header shows the source, counts, the last poll duration and the current
interval.

## How it works

A small rclpy node (hidden, `/_rosgraph_tui_<pid>`) reads the rmw discovery
cache: `get_node_names_and_namespaces`, `get_topic_names_and_types` and, per
node, `get_publisher_names_and_types_by_node` / `get_subscriber_names_and_types_by_node`.
Nothing is spun, no daemon is involved, and discovery is asynchronous, so the
graph fills in during the first second or two after start. QoS is fetched with
`get_publishers_info_by_topic` / `get_subscriptions_info_by_topic` only for the
topic under the cursor.

Polling runs in a worker thread and produces an immutable, fully indexed
snapshot; the UI only swaps the reference. Unchanged snapshots (same content
hash) do not touch the UI at all.

## Development

With [uv](https://docs.astral.sh/uv/) (recommended; `uv.lock` pins the dev
environment; install uv with `pipx install uv` or the
[standalone installer](https://docs.astral.sh/uv/getting-started/installation/)):

```zsh
git clone -b ros2_port https://github.com/orzechow/rosgraph_tui && cd rosgraph_tui
uv sync                     # creates .venv with the package and the dev tools
uv run pytest               # unit, Textual pilot and perf tests; no ROS 2 needed
uv run ruff check rosgraph_tui test scripts
uv run rosgraph_tui --demo  # or: --fixture path/to/graph.json
```

With plain venv + pip:

```zsh
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'     # the quotes matter in zsh, where [dev] is a glob
pytest
```

With a sourced ROS 2 installation the `test/ros` integration test and the poll
benchmark also run. rclpy is found through `PYTHONPATH`, which the ROS setup
script exports, so the same environment works:

```zsh
source /opt/ros/jazzy/setup.zsh
uv run pytest -m ros
uv run python scripts/bench_poll.py --nodes 200 --topics-per-node 10
```

CI runs the same in a `ros:jazzy-ros-core` container together with a colcon
build. Fixture files use the format of
[`rosgraph_tui/fixtures/demo.json`](rosgraph_tui/fixtures/demo.json).

## Roadmap

- services and actions as additional entity kinds
- `hz` / `bw` / `delay` for the topic under the cursor
- copy the highlighted name to the clipboard

## License

MIT
