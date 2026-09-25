from rosgraph_tui.model import Endpoint, EntityRef, Kind, QosSummary, RawGraph, build_snapshot
from rosgraph_tui.viewmodel import (
    ViewState,
    backspace,
    choose,
    derive_view,
    escape,
    info_line,
    toggle_hidden,
    type_char,
)

TALKER = EntityRef(Kind.NODE, "/talker")
LISTENER = EntityRef(Kind.NODE, "/listener")
CHATTER = EntityRef(Kind.TOPIC, "/chatter")
DAEMON = EntityRef(Kind.NODE, "/_ros2cli_daemon_0")


def refs(column):
    return [r.ref for r in column.rows]


def test_discovering_when_no_snapshot():
    vm = derive_view(None, ViewState())
    assert vm.status == "Discovering…"
    assert vm.middle.rows == ()
    assert derive_view(build_snapshot(RawGraph()), ViewState()).status == "Discovering…"


def test_unrooted_lists_nodes_then_topics(demo_snapshot):
    vm = derive_view(demo_snapshot, ViewState())
    kinds = [r.ref.kind for r in vm.middle.rows]
    assert kinds == sorted(kinds, key=lambda k: list(Kind).index(k))
    assert vm.middle.title.startswith("Nodes and Topics (")
    assert vm.left.rows == () and vm.right.rows == ()
    assert DAEMON not in refs(vm.middle)
    assert vm.middle.rows[0].label.startswith("N /")


def test_scope_restricts_kind(demo_snapshot):
    vm = derive_view(demo_snapshot, ViewState(scope=Kind.TOPIC))
    assert all(r.ref.kind is Kind.TOPIC for r in vm.middle.rows)
    assert vm.middle.title.startswith("Topics (")


def test_filter_orders_best_match_first(demo_snapshot):
    vm = derive_view(demo_snapshot, ViewState(filter_text="chatter"))
    assert refs(vm.middle)[0] == CHATTER
    assert vm.middle.info == "chatter"
    assert LISTENER not in refs(vm.middle)


def test_rooted_on_node(demo_snapshot):
    vm = derive_view(demo_snapshot, choose(ViewState(), TALKER))
    assert refs(vm.middle) == [TALKER]
    assert vm.middle.rows[0].style == "chosen"
    assert vm.left.title.startswith("Subscriptions (0)")
    assert vm.right.title.startswith("Publications (3)")
    assert CHATTER in refs(vm.right)


def test_rooted_on_topic(demo_snapshot):
    vm = derive_view(demo_snapshot, choose(ViewState(), CHATTER))
    assert refs(vm.left) == [TALKER]
    assert refs(vm.right) == [LISTENER]
    assert vm.left.title.startswith("Publishers")
    assert vm.right.title.startswith("Subscribers")


def test_filter_applies_to_side_columns_when_rooted(demo_snapshot):
    state = ViewState(root=TALKER, scope=Kind.NODE, filter_text="chat")
    vm = derive_view(demo_snapshot, state)
    assert refs(vm.right) == [CHATTER]
    assert refs(vm.middle) == [TALKER]


def test_unconnected_styles(demo_snapshot):
    diag = EntityRef(Kind.TOPIC, "/diagnostics")
    controller = EntityRef(Kind.NODE, "/control/controller")
    vm = derive_view(demo_snapshot, choose(ViewState(), controller))
    styles = {r.ref: r.style for r in vm.right.rows}
    assert styles[diag] == "unconnected"  # published, nobody subscribes
    assert styles[EntityRef(Kind.TOPIC, "/control/cmd_vel")] == "topic"


def test_gone_root(demo_snapshot):
    ghost = EntityRef(Kind.NODE, "/ghost")
    vm = derive_view(demo_snapshot, choose(ViewState(), ghost))
    assert vm.middle.rows[0].style == "gone"
    assert vm.status == "root gone"
    assert vm.left.rows == ()


def test_hidden_toggle(demo_snapshot):
    state = toggle_hidden(ViewState())
    vm = derive_view(demo_snapshot, state)
    assert DAEMON in refs(vm.middle)
    styles = {r.ref: r.style for r in vm.middle.rows}
    assert styles[DAEMON] == "hidden"


def test_escape_chain():
    s = ViewState(root=TALKER, scope=Kind.NODE, filter_text="x")
    s = escape(s)
    assert s.filter_text == "" and s.root == TALKER
    s = escape(s)
    assert s.root is None and s.scope is Kind.NODE
    s = escape(s)
    assert s.scope is None
    assert escape(s) is None


def test_typing():
    s = type_char(ViewState(), "a")
    s = type_char(s, "/")
    assert s.filter_text == "a/"
    assert type_char(s, "enter") is None
    assert type_char(s, " ") is None
    assert backspace(s).filter_text == "a"


def test_choose_clears_filter():
    s = choose(ViewState(filter_text="abc"), CHATTER)
    assert s.filter_text == "" and s.root == CHATTER and s.scope is Kind.TOPIC


def test_derive_view_is_memoised(demo_snapshot):
    a = derive_view(demo_snapshot, ViewState(filter_text="cam"))
    b = derive_view(demo_snapshot, ViewState(filter_text="cam"))
    assert a is b


def test_info_line(demo_snapshot):
    chatter = demo_snapshot.get(CHATTER)
    assert info_line(chatter) == "Type: std_msgs/msg/String · 1 pubs / 1 subs"
    eps = [Endpoint(TALKER, True, "std_msgs/msg/String", QosSummary("reliable", "volatile"))]
    assert info_line(chatter, eps).endswith("QoS: reliable / volatile")
    listener = demo_snapshot.get(LISTENER)
    assert info_line(listener) == "1 subs / 1 pubs · 2 instances"
    assert info_line(None) == ""


def test_preview_shows_inputs_and_outputs(demo_snapshot):
    from rosgraph_tui.viewmodel import set_preview

    vm = derive_view(demo_snapshot, set_preview(ViewState(), CHATTER))
    assert refs(vm.left) == [TALKER] and refs(vm.right) == [LISTENER]
    assert vm.left.title.startswith("Publishers (1)")
    assert vm.right.title.startswith("Subscribers (1)")
    # the middle column is unaffected by the preview
    assert refs(vm.middle) == refs(derive_view(demo_snapshot, ViewState()).middle)


def test_preview_ignores_filter_and_is_dropped_when_rooted(demo_snapshot):
    from rosgraph_tui.viewmodel import set_preview

    state = set_preview(ViewState(filter_text="zzz"), TALKER)
    vm = derive_view(demo_snapshot, state)
    assert len(refs(vm.right)) == 3  # publications of /talker, not filtered by "zzz"
    rooted = derive_view(demo_snapshot, choose(state, CHATTER))
    assert refs(rooted.left) == [TALKER]


def test_preview_of_missing_or_hidden_entry_is_empty(demo_snapshot):
    from rosgraph_tui.viewmodel import set_preview

    vm = derive_view(demo_snapshot, set_preview(ViewState(), EntityRef(Kind.NODE, "/ghost")))
    assert vm.left.rows == () and vm.left.title == "Input:"
    vm = derive_view(demo_snapshot, set_preview(ViewState(), DAEMON))
    assert vm.right.rows == ()
    vm = derive_view(demo_snapshot, set_preview(ViewState(include_hidden=True), DAEMON))
    assert len(vm.right.rows) == 2


def test_set_preview_is_identity_when_unchanged():
    from rosgraph_tui.viewmodel import set_preview

    s = set_preview(ViewState(), TALKER)
    assert set_preview(s, TALKER) is s


def test_middle_refs_cached_across_preview_changes(demo_snapshot):
    from rosgraph_tui.viewmodel import _middle_refs, set_preview

    _middle_refs.cache_clear()
    derive_view(demo_snapshot, set_preview(ViewState(filter_text="cam"), TALKER))
    derive_view(demo_snapshot, set_preview(ViewState(filter_text="cam"), CHATTER))
    assert _middle_refs.cache_info().hits >= 1
