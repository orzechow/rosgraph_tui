from rosgraph_tui.model import EntityRef, Kind, RawGraph, build_snapshot, is_hidden, join_fqn


def test_join_fqn():
    assert join_fqn("/", "talker") == "/talker"
    assert join_fqn("/ns", "n") == "/ns/n"
    assert join_fqn("/ns/", "n") == "/ns/n"
    assert join_fqn("/a/b", "/c") == "/a/b/c"


def test_is_hidden():
    assert is_hidden("/_ros2cli_1")
    assert is_hidden("/ns/_x/y")
    assert is_hidden("/_internal/heartbeat")
    assert not is_hidden("/rosout")
    assert not is_hidden("/parameter_events")
    assert not is_hidden("/a_b/c_d")


def test_build_snapshot_edges(tiny_raw):
    snap = build_snapshot(tiny_raw)
    talker = snap.get(EntityRef(Kind.NODE, "/talker"))
    listener = snap.get(EntityRef(Kind.NODE, "/ns/listener"))
    chatter = snap.get(EntityRef(Kind.TOPIC, "/chatter"))
    assert talker.outputs == (chatter.ref,)
    assert talker.inputs == ()
    assert listener.inputs == (chatter.ref,)
    assert chatter.inputs == (talker.ref,)
    assert chatter.outputs == (listener.ref,)
    assert chatter.types == ("std_msgs/msg/String",)
    assert snap.count(Kind.NODE) == 2
    assert snap.count(Kind.TOPIC) == 1
    assert snap.names(None) == ["/ns/listener", "/talker", "/chatter"]


def test_duplicate_nodes_and_multi_type_topics():
    raw = RawGraph(
        nodes=[("n", "/"), ("n", "/")],
        topics=[("/t", ["A"]), ("/t", ["B"])],
        node_pubs={"/n": [("/t", ["A", "B"])]},
    )
    snap = build_snapshot(raw)
    assert snap.get(EntityRef(Kind.NODE, "/n")).instances == 2
    assert snap.get(EntityRef(Kind.TOPIC, "/t")).types == ("A", "B")


def test_topic_only_known_from_edges_is_created():
    raw = RawGraph(nodes=[("n", "/")], node_subs={"/n": [("/late", ["X"])]})
    snap = build_snapshot(raw)
    assert EntityRef(Kind.TOPIC, "/late") in snap
    assert snap.get(EntityRef(Kind.TOPIC, "/late")).outputs == (EntityRef(Kind.NODE, "/n"),)


def test_node_only_known_from_edges_is_created():
    raw = RawGraph(node_pubs={"/ghost": [("/t", ["X"])]})
    snap = build_snapshot(raw)
    assert EntityRef(Kind.NODE, "/ghost") in snap


def test_unconnected_topic(demo_snapshot):
    diag = demo_snapshot.get(EntityRef(Kind.TOPIC, "/diagnostics"))
    assert diag.inputs and not diag.outputs
    assert not diag.unconnected
    hb = demo_snapshot.get(EntityRef(Kind.TOPIC, "/_internal/heartbeat"))
    assert hb.hidden


def test_visible_drops_hidden_entities_and_their_edges(demo_snapshot):
    vis = demo_snapshot.visible(False)
    assert EntityRef(Kind.NODE, "/_ros2cli_daemon_0") not in vis
    assert EntityRef(Kind.TOPIC, "/_internal/heartbeat") not in vis
    rosout = vis.get(EntityRef(Kind.TOPIC, "/rosout"))
    assert EntityRef(Kind.NODE, "/_ros2cli_daemon_0") not in rosout.inputs
    assert EntityRef(Kind.NODE, "/talker") in rosout.inputs
    # unchanged when hidden entities are included
    assert demo_snapshot.visible(True) is demo_snapshot
    # cached
    assert demo_snapshot.visible(False) is vis


def test_digest_is_order_independent():
    a = RawGraph(nodes=[("a", "/"), ("b", "/")], node_pubs={"/a": [("/t", ["X", "Y"])]})
    b = RawGraph(nodes=[("b", "/"), ("a", "/")], node_pubs={"/a": [("/t", ["Y", "X"])]})
    c = RawGraph(nodes=[("b", "/"), ("a", "/")], node_pubs={"/a": [("/t", ["Y"])]})
    assert a.digest() == b.digest()
    assert a.digest() != c.digest()
