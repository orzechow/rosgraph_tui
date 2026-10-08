import pytest

from rosgraph_tui.model import RawGraph
from rosgraph_tui.source import FakeGraphSource, demo_source


@pytest.fixture
def demo():
    return demo_source()


@pytest.fixture
def demo_snapshot(demo):
    return demo.snapshot()


@pytest.fixture
def tiny_raw():
    return RawGraph(
        nodes=[("talker", "/"), ("listener", "/ns")],
        topics=[("/chatter", ["std_msgs/msg/String"])],
        node_pubs={"/talker": [("/chatter", ["std_msgs/msg/String"])]},
        node_subs={"/ns/listener": [("/chatter", ["std_msgs/msg/String"])]},
    )


@pytest.fixture
def tiny_source(tiny_raw):
    return FakeGraphSource(tiny_raw)
