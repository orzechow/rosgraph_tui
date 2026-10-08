import json

from rosgraph_tui.model import EntityRef, Kind, QosSummary, RawGraph
from rosgraph_tui.source import FakeGraphSource, demo_source


def test_demo_source_loads():
    src = demo_source()
    snap = src.snapshot()
    assert src.describe() == "demo"
    assert snap.count(Kind.NODE) >= 8
    assert EntityRef(Kind.NODE, "/camera/driver") in snap
    assert snap.get(EntityRef(Kind.NODE, "/listener")).instances == 2


def test_set_raw_invalidates_snapshot(tiny_source):
    first = tiny_source.snapshot()
    assert tiny_source.snapshot() is first
    tiny_source.set_raw(RawGraph(nodes=[("only", "/")]))
    second = tiny_source.snapshot()
    assert second is not first
    assert second.names(Kind.NODE) == ["/only"]
    assert tiny_source.poll_count == 3


def test_topic_endpoints_with_qos():
    src = demo_source()
    eps = src.topic_endpoints("/chatter")
    pubs = [e for e in eps if e.is_publisher]
    subs = [e for e in eps if not e.is_publisher]
    assert [e.node.name for e in pubs] == ["/talker"]
    assert [e.node.name for e in subs] == ["/listener"]
    assert pubs[0].qos == QosSummary("reliable", "volatile")
    assert pubs[0].type == "std_msgs/msg/String"
    assert src.topic_endpoints("/rosout")[0].qos is None


def test_from_json(tmp_path):
    path = tmp_path / "g.json"
    path.write_text(
        json.dumps(
            {
                "nodes": [{"name": "n", "namespace": "/ns"}],
                "publications": [{"node": "n", "namespace": "/ns", "topic": "/t", "types": ["A"]}],
            }
        )
    )
    src = FakeGraphSource.from_json(path)
    snap = src.snapshot()
    assert snap.get(EntityRef(Kind.NODE, "/ns/n")).outputs == (EntityRef(Kind.TOPIC, "/t"),)
    assert src.describe() == "g.json"
