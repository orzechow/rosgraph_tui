"""Integration test against a real rclpy graph.  Needs a sourced ROS 2 installation."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

rclpy = pytest.importorskip("rclpy")

from rosgraph_tui.model import EntityRef, Kind  # noqa: E402
from rosgraph_tui.rclpy_source import RclpyGraphSource  # noqa: E402
from rosgraph_tui.source import SourceError  # noqa: E402

pytestmark = pytest.mark.ros

TALKER = EntityRef(Kind.NODE, "/it/talker")
LISTENER = EntityRef(Kind.NODE, "/it/listener")
CHATTER = EntityRef(Kind.TOPIC, "/it/chatter")
SCRIPT = Path(__file__).with_name("talker_listener.py")


def start_process(*args: str) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    assert proc.stdout is not None
    line = proc.stdout.readline()
    assert "ready" in line, line
    return proc


def wait_for(source: RclpyGraphSource, predicate, timeout: float = 15.0):
    deadline = time.time() + timeout
    while True:
        snapshot = source.snapshot(full=True)
        if predicate(snapshot):
            return snapshot
        if time.time() > deadline:
            pytest.fail("timed out waiting for the graph to contain the test nodes")
        time.sleep(0.5)


@pytest.fixture(scope="module")
def processes():
    os.environ.setdefault("ROS_DOMAIN_ID", "42")
    os.environ.setdefault("ROS_AUTOMATIC_DISCOVERY_RANGE", "LOCALHOST")
    first = start_process()
    second = start_process()  # duplicates /it/talker and /it/listener on purpose
    yield first, second
    for proc in (first, second):
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="module")
def source(processes):
    src = RclpyGraphSource(node_name="_rosgraph_tui_test")
    yield src
    src.close()
    src.close()  # idempotent


def test_edges_types_and_duplicates(source):
    snap = wait_for(source, lambda s: TALKER in s and LISTENER in s and CHATTER in s)
    talker = snap.get(TALKER)
    listener = snap.get(LISTENER)
    chatter = snap.get(CHATTER)
    assert CHATTER in talker.outputs
    assert CHATTER in listener.inputs
    assert TALKER in chatter.inputs and LISTENER in chatter.outputs
    assert chatter.types == ("std_msgs/msg/String",)
    assert talker.instances == 2
    assert snap.poll_ms > 0


def test_own_node_is_hidden(source):
    snap = source.snapshot()
    me = EntityRef(Kind.NODE, "/_rosgraph_tui_test")
    assert me in snap
    assert snap.get(me).hidden
    assert me not in snap.visible(False)


def test_lazy_qos(source):
    wait_for(source, lambda s: CHATTER in s)
    endpoints = source.topic_endpoints("/it/chatter")
    pubs = [e for e in endpoints if e.is_publisher]
    subs = [e for e in endpoints if not e.is_publisher]
    assert {e.node for e in pubs} == {TALKER}
    assert {e.node for e in subs} == {LISTENER}
    assert pubs[0].type == "std_msgs/msg/String"
    assert pubs[0].qos.reliability == "reliable"
    assert pubs[0].qos.durability == "transient_local"


def test_cheap_poll_reuses_snapshot_when_lists_unchanged(source):
    full = source.snapshot(full=True)
    cheap = source.snapshot(full=False)
    assert cheap is full or cheap.digest == full.digest


def test_describe(source):
    assert source.describe().startswith("ROS 2 domain")


def test_closed_source_raises(processes):
    src = RclpyGraphSource(node_name="_rosgraph_tui_test2")
    src.close()
    with pytest.raises(SourceError):
        src.snapshot()
