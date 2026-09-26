"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from rosgraph_tui import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rosgraph_tui",
        description="Explore and debug your ROS 2 graph interactively in the terminal.",
        epilog="Type to filter, use the arrow keys to walk the graph, Esc to go back, Ctrl+Q to quit. "
        "Everything after --ros-args is passed to rclpy (e.g. --ros-args -r __node:=my_tui).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--demo", action="store_true", help="explore a bundled example graph without ROS 2")
    parser.add_argument("--fixture", metavar="PATH", help="explore a graph loaded from a JSON fixture file")
    parser.add_argument(
        "--include-hidden", action="store_true", help="show hidden nodes and topics (names with a '_' token)"
    )
    parser.add_argument(
        "--refresh-rate",
        type=float,
        default=1.0,
        metavar="HZ",
        help="how often to poll the graph (default: 1.0; 0 disables automatic refresh)",
    )
    parser.add_argument(
        "--full-poll-every",
        type=int,
        default=5,
        metavar="N",
        help="re-read every node's connections at least every N polls even when the node and "
        "topic lists did not change (default: 5)",
    )
    return parser


def split_ros_args(argv: Sequence[str]) -> tuple[list[str], list[str]]:
    """Split ``argv`` into (our arguments, the full argv to hand to rclpy)."""
    argv = list(argv)
    if "--ros-args" in argv:
        return argv[: argv.index("--ros-args")], argv
    return argv, argv


def make_source(args: argparse.Namespace, full_argv: list[str]):
    from rosgraph_tui.source import FakeGraphSource, demo_source

    if args.demo:
        return demo_source()
    if args.fixture:
        return FakeGraphSource.from_json(args.fixture)
    from rosgraph_tui.rclpy_source import RclpyGraphSource

    return RclpyGraphSource(argv=full_argv, full_every=max(1, args.full_poll_every))


def main(argv: Sequence[str] | None = None) -> int:
    from rosgraph_tui.source import SourceError

    argv = list(sys.argv[1:] if argv is None else argv)
    own_args, full_argv = split_ros_args(argv)
    args = build_parser().parse_args(own_args)

    try:
        source = make_source(args, full_argv)
    except SourceError as exc:
        print(f"\033[31merror: {exc}\033[0m", file=sys.stderr)
        return 1

    from rosgraph_tui.app import RosgraphApp

    app = RosgraphApp(source, include_hidden=args.include_hidden, refresh_rate=args.refresh_rate)
    try:
        app.run()
    finally:
        source.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
