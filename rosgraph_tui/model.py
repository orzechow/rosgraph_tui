"""Graph data model: entities, snapshots and the ROS-shaped raw graph.

Everything here is pure Python with no ROS dependency, so it can be built
from an rclpy poll, from a JSON fixture or from a synthetic generator, and
can be tested without a ROS 2 installation.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property


class Kind(str, Enum):
    """Entity kinds.  Services and actions can be added later."""

    NODE = "node"
    TOPIC = "topic"

    @property
    def prefix(self) -> str:
        return "N" if self is Kind.NODE else "T"

    @property
    def title(self) -> str:
        return self.value.capitalize()


@dataclass(frozen=True, order=True)
class EntityRef:
    """Identity of an entity: kind plus fully qualified name."""

    kind: Kind
    name: str

    @property
    def label(self) -> str:
        return f"{self.kind.prefix} {self.name}"

    @property
    def id(self) -> str:
        return f"{self.kind.value}:{self.name}"


@dataclass(frozen=True)
class QosSummary:
    reliability: str
    durability: str

    def __str__(self) -> str:
        return f"{self.reliability} / {self.durability}"


@dataclass(frozen=True)
class Endpoint:
    """One publisher or subscription on a topic (lazily fetched, carries QoS)."""

    node: EntityRef
    is_publisher: bool
    type: str
    qos: QosSummary | None


@dataclass(frozen=True)
class Entity:
    ref: EntityRef
    types: tuple[str, ...] = ()
    inputs: tuple[EntityRef, ...] = ()
    outputs: tuple[EntityRef, ...] = ()
    hidden: bool = False
    instances: int = 1

    @property
    def name(self) -> str:
        return self.ref.name

    @property
    def kind(self) -> Kind:
        return self.ref.kind

    @property
    def unconnected(self) -> bool:
        return not self.inputs and not self.outputs


def join_fqn(namespace: str, name: str) -> str:
    """Join a ROS 2 (namespace, name) pair into a fully qualified name."""
    ns = namespace.rstrip("/")
    name = name.lstrip("/")
    return f"{ns}/{name}"


def is_hidden(name: str) -> bool:
    """ros2cli convention: a name is hidden if any token starts with '_'."""
    return any(token.startswith("_") for token in name.split("/") if token)


@dataclass
class RawGraph:
    """What a poll of the ROS graph returns, before any interpretation.

    ``node_pubs`` and ``node_subs`` map a node's fully qualified name to the
    ``(topic, [types])`` pairs returned by the per-node rclpy calls.
    """

    nodes: list[tuple[str, str]] = field(default_factory=list)  # (name, namespace)
    topics: list[tuple[str, list[str]]] = field(default_factory=list)  # (fqn, types)
    node_pubs: dict[str, list[tuple[str, list[str]]]] = field(default_factory=dict)
    node_subs: dict[str, list[tuple[str, list[str]]]] = field(default_factory=dict)

    def digest(self) -> int:
        """Cheap content hash so unchanged polls skip all UI work."""
        return hash(
            (
                tuple(sorted(self.nodes)),
                tuple((t, tuple(sorted(ty))) for t, ty in sorted(self.topics)),
                tuple(
                    (n, tuple((t, tuple(sorted(ty))) for t, ty in sorted(v)))
                    for n, v in sorted(self.node_pubs.items())
                ),
                tuple(
                    (n, tuple((t, tuple(sorted(ty))) for t, ty in sorted(v)))
                    for n, v in sorted(self.node_subs.items())
                ),
            )
        )


@dataclass(frozen=True, eq=False)
class GraphSnapshot:
    """Immutable, fully indexed view of the graph at one point in time.

    ``eq=False`` keeps identity hashing so snapshots can key an LRU cache.
    """

    entities: dict[EntityRef, Entity]
    taken_at: float = 0.0
    digest: int = 0
    poll_ms: float = 0.0

    def get(self, ref: EntityRef) -> Entity | None:
        return self.entities.get(ref)

    def __contains__(self, ref: object) -> bool:
        return ref in self.entities

    @cached_property
    def _visible(self) -> GraphSnapshot:
        keep = {ref for ref, e in self.entities.items() if not e.hidden}
        entities = {
            ref: Entity(
                ref=e.ref,
                types=e.types,
                inputs=tuple(r for r in e.inputs if r in keep),
                outputs=tuple(r for r in e.outputs if r in keep),
                hidden=False,
                instances=e.instances,
            )
            for ref, e in self.entities.items()
            if ref in keep
        }
        return GraphSnapshot(entities, self.taken_at, self.digest, self.poll_ms)

    def visible(self, include_hidden: bool) -> GraphSnapshot:
        return self if include_hidden else self._visible

    @cached_property
    def _names_by_kind(self) -> dict[Kind | None, list[str]]:
        result: dict[Kind | None, list[str]] = {}
        for kind in Kind:
            result[kind] = sorted(r.name for r in self.entities if r.kind == kind)
        return result

    def names(self, kind: Kind | None) -> list[str]:
        """Sorted names of one kind (cached), or of all kinds when ``kind`` is None."""
        if kind is not None:
            return self._names_by_kind[kind]
        return [n for k in Kind for n in self._names_by_kind[k]]

    def count(self, kind: Kind) -> int:
        return len(self._names_by_kind[kind])

    def of_kind(self, kind: Kind | None) -> list[Entity]:
        return [e for e in self.entities.values() if kind is None or e.kind == kind]


def build_snapshot(raw: RawGraph, taken_at: float | None = None, poll_ms: float = 0.0) -> GraphSnapshot:
    """Index a raw poll into a snapshot.  O(nodes + topics + edges)."""
    node_counts = Counter(join_fqn(ns, name) for name, ns in raw.nodes)
    topic_types: dict[str, set] = defaultdict(set)
    for topic, types in raw.topics:
        topic_types[topic].update(types)

    node_inputs: dict[str, set] = defaultdict(set)
    node_outputs: dict[str, set] = defaultdict(set)
    topic_inputs: dict[str, set] = defaultdict(set)  # publishers
    topic_outputs: dict[str, set] = defaultdict(set)  # subscribers

    for node, pubs in raw.node_pubs.items():
        node_counts.setdefault(node, 1)
        for topic, types in pubs:
            topic_types[topic].update(types)
            node_outputs[node].add(topic)
            topic_inputs[topic].add(node)
    for node, subs in raw.node_subs.items():
        node_counts.setdefault(node, 1)
        for topic, types in subs:
            topic_types[topic].update(types)
            node_inputs[node].add(topic)
            topic_outputs[topic].add(node)

    def refs(kind: Kind, names: Iterable[str]) -> tuple[EntityRef, ...]:
        return tuple(EntityRef(kind, n) for n in sorted(names))

    entities: dict[EntityRef, Entity] = {}
    for name, count in node_counts.items():
        ref = EntityRef(Kind.NODE, name)
        entities[ref] = Entity(
            ref=ref,
            inputs=refs(Kind.TOPIC, node_inputs.get(name, ())),
            outputs=refs(Kind.TOPIC, node_outputs.get(name, ())),
            hidden=is_hidden(name),
            instances=count,
        )
    for name, types in topic_types.items():
        ref = EntityRef(Kind.TOPIC, name)
        entities[ref] = Entity(
            ref=ref,
            types=tuple(sorted(types)),
            inputs=refs(Kind.NODE, topic_inputs.get(name, ())),
            outputs=refs(Kind.NODE, topic_outputs.get(name, ())),
            hidden=is_hidden(name),
        )

    return GraphSnapshot(
        entities=entities,
        taken_at=time.time() if taken_at is None else taken_at,
        digest=raw.digest(),
        poll_ms=poll_ms,
    )


def empty_snapshot() -> GraphSnapshot:
    return GraphSnapshot(entities={}, taken_at=0.0)
