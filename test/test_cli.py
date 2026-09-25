import subprocess
import sys

import pytest

from rosgraph_tui.cli import build_parser, make_source, split_ros_args


def test_split_ros_args():
    assert split_ros_args(["--demo"]) == (["--demo"], ["--demo"])
    own, full = split_ros_args(["--include-hidden", "--ros-args", "-r", "__node:=x"])
    assert own == ["--include-hidden"]
    assert full == ["--include-hidden", "--ros-args", "-r", "__node:=x"]


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.refresh_rate == 1.0
    assert args.full_poll_every == 5
    assert not args.demo and not args.include_hidden


def test_demo_source_does_not_import_rclpy():
    code = (
        "import sys; from rosgraph_tui.cli import build_parser, make_source; "
        "src = make_source(build_parser().parse_args(['--demo']), ['--demo']); "
        "assert src.describe() == 'demo'; assert 'rclpy' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_fixture_source(tmp_path):
    path = tmp_path / "g.json"
    path.write_text('{"nodes": [{"name": "a", "namespace": "/"}]}')
    args = build_parser().parse_args(["--fixture", str(path)])
    assert make_source(args, []).snapshot().names(None) == ["/a"]


def test_missing_rclpy_error_message(monkeypatch):
    import rosgraph_tui.rclpy_source as mod
    from rosgraph_tui.source import SourceError

    monkeypatch.setattr(mod, "rclpy", None)
    with pytest.raises(SourceError, match="source /opt/ros"):
        mod.RclpyGraphSource()
