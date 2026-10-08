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


def test_main_propagates_the_app_return_code(monkeypatch):
    import rosgraph_tui.app as app_module
    from rosgraph_tui.cli import main

    class StubApp:
        def __init__(self, source, include_hidden, refresh_rate):
            self.return_code = None

        def run(self):
            self.return_code = 2

    monkeypatch.setattr(app_module, "RosgraphApp", StubApp)
    assert main(["--demo"]) == 2

    class CleanApp(StubApp):
        def run(self):
            self.return_code = None

    monkeypatch.setattr(app_module, "RosgraphApp", CleanApp)
    assert main(["--demo"]) == 0


def test_bad_fixture_gives_a_one_line_error(tmp_path, capsys):
    from rosgraph_tui.cli import main

    assert main(["--fixture", str(tmp_path / "missing.json")]) == 1
    err = capsys.readouterr().err
    assert "could not load fixture" in err and "missing.json" in err and "Traceback" not in err

    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert main(["--fixture", str(bad)]) == 1
    assert "could not load fixture" in capsys.readouterr().err

    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text('{"nodes": [{"namespace": "/"}]}')
    assert main(["--fixture", str(incomplete)]) == 1
    assert "could not load fixture" in capsys.readouterr().err
