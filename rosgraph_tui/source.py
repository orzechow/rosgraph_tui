"""Graph sources: where snapshots come from.

``GraphSource`` is the only thing the UI talks to.  ``FakeGraphSource`` serves
fixtures for tests, the ``--demo`` mode and development without ROS 2; the
rclpy implementation lives in :mod:`rosgraph_tui.rclpy_source`.
"""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from importlib import resources
from pathlib import Path

from rosgraph_tui.model import (
    Endpoint,
    EntityRef,
    GraphSnapshot,
    Kind,
    QosSummary,
    RawGraph,
    build_snapshot,
    join_fqn,
)


class SourceError(RuntimeError):
    """Raised when a source cannot be created or polled."""


class GraphSource(ABC):
    """A pollable view of a ROS graph.  Methods may be called from a worker thread."""

    @abstractmethod
    def snapshot(self, full: bool = True) -> GraphSnapshot:
        """Poll the graph.  ``full=False`` allows a cheaper check that may
        return the previous snapshot when nothing changed."""

    @abstractmethod
    def topic_endpoints(self, topic: str) -> list[Endpoint]:
        """Publishers and subscriptions of one topic, with QoS.  Fetched lazily."""

    def close(self) -> None:
        """Release resources.  Must be idempotent."""
        return None

    def describe(self) -> str:
        return type(self).__name__


class FakeGraphSource(GraphSource):
    """In-memory source fed from a ``RawGraph`` (plus optional QoS per endpoint)."""

    def __init__(self, raw: RawGraph, qos: dict[tuple, QosSummary] | None = None, name: str = "fake"):
        self._lock = threading.Lock()
        self._raw = raw
        self._qos: dict[tuple, QosSummary] = dict(qos or {})
        self._name = name
        self._snapshot: GraphSnapshot | None = None
        self.poll_count = 0

    def set_raw(self, raw: RawGraph, qos: dict[tuple, QosSummary] | None = None) -> None:
        """Replace the graph, simulating a change in the live system."""
        with self._lock:
            self._raw = raw
            if qos is not None:
                self._qos = dict(qos)
            self._snapshot = None

    def snapshot(self, full: bool = True) -> GraphSnapshot:
        with self._lock:
            self.poll_count += 1
            if self._snapshot is None:
                self._snapshot = build_snapshot(self._raw)
            return self._snapshot

    def topic_endpoints(self, topic: str) -> list[Endpoint]:
        with self._lock:
            result: list[Endpoint] = []
            for node, pubs in self._raw.node_pubs.items():
                for t, types in pubs:
                    if t == topic:
                        for ty in types or [""]:
                            qos = self._qos.get((node, topic, True))
                            result.append(Endpoint(EntityRef(Kind.NODE, node), True, ty, qos))
            for node, subs in self._raw.node_subs.items():
                for t, types in subs:
                    if t == topic:
                        for ty in types or [""]:
                            qos = self._qos.get((node, topic, False))
                            result.append(Endpoint(EntityRef(Kind.NODE, node), False, ty, qos))
            return result

    def describe(self) -> str:
        return self._name

    @classmethod
    def from_dict(cls, data: dict, name: str = "fixture") -> FakeGraphSource:
        raw, qos = raw_graph_from_dict(data)
        return cls(raw, qos, name=name)

    @classmethod
    def from_json(cls, path: str | Path) -> FakeGraphSource:
        path = Path(path)
        with path.open() as fh:
            return cls.from_dict(json.load(fh), name=path.name)


def raw_graph_from_dict(data: dict):
    """Parse the fixture JSON format.

    ::

        {"nodes": [{"name": "talker", "namespace": "/"}],
         "topics": [{"name": "/chatter", "types": ["std_msgs/msg/String"]}],
         "publications": [{"node": "/talker", "topic": "/chatter",
                           "type": "std_msgs/msg/String",
                           "qos": {"reliability": "reliable", "durability": "volatile"}}],
         "subscriptions": [...]}

    ``node`` in publications/subscriptions is the fully qualified node name.
    """
    raw = RawGraph()
    qos: dict[tuple, QosSummary] = {}
    for node in data.get("nodes", []):
        raw.nodes.append((node["name"], node.get("namespace", "/")))
    for topic in data.get("topics", []):
        raw.topics.append((topic["name"], list(topic.get("types", []))))
    edge_lists = (("publications", raw.node_pubs, True), ("subscriptions", raw.node_subs, False))
    for key, target, is_pub in edge_lists:
        for edge in data.get(key, []):
            node = edge["node"]
            if "namespace" in edge:
                node = join_fqn(edge["namespace"], node)
            types = [edge["type"]] if "type" in edge else list(edge.get("types", []))
            target.setdefault(node, []).append((edge["topic"], types))
            if "qos" in edge:
                q = edge["qos"]
                qos[(node, edge["topic"], is_pub)] = QosSummary(
                    q.get("reliability", "unknown"), q.get("durability", "unknown")
                )
    return raw, qos


def demo_source() -> FakeGraphSource:
    """The bundled demo graph, for ``--demo`` and for tests."""
    text = resources.files("rosgraph_tui").joinpath("fixtures/demo.json").read_text()
    return FakeGraphSource.from_dict(json.loads(text), name="demo")
