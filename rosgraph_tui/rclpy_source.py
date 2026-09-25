"""The rclpy-backed graph source.  This is the only module that imports rclpy.

Design for large graphs (hundreds of nodes, thousands of topics):

* A poll costs two calls per *node* (publisher and subscriber lists), never
  per topic.  QoS, which is only available per topic endpoint, is fetched
  lazily for the one topic the user is looking at.
* A cheap poll (``full=False``) first compares the node and topic lists with
  the previous poll and skips the per-node phase when they are unchanged,
  except every ``full_every``-th poll, because a node can add a subscription
  to an existing topic without changing either list.
* No executor is spun: all graph queries read the rmw discovery cache.
* The loop yields the GIL every few dozen calls so the UI keeps repainting.
"""

from __future__ import annotations

import inspect
import os
import threading
import time
from collections.abc import Sequence

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
from rosgraph_tui.source import GraphSource, SourceError

try:
    import rclpy
    from rclpy.node import Node
except ImportError:  # pragma: no cover - exercised only without ROS 2
    rclpy = None
    Node = None

YIELD_EVERY = 40

MISSING_RCLPY = (
    "rclpy not found. Source your ROS 2 installation first "
    "(e.g. `source /opt/ros/jazzy/setup.bash`), or run with --demo."
)


def _policy_name(policy: object) -> str:
    name = getattr(policy, "name", None) or str(policy)
    return name.lower().replace("rmw_qos_", "").replace("_policy", "")


def _qos_summary(profile: object) -> QosSummary | None:
    if profile is None:
        return None
    reliability = getattr(profile, "reliability", None)
    durability = getattr(profile, "durability", None)
    if reliability is None and durability is None:
        return None
    return QosSummary(_policy_name(reliability), _policy_name(durability))


def _merge(target: dict[str, list[str]], pairs: Sequence[tuple[str, Sequence[str]]]) -> None:
    for topic, types in pairs:
        target.setdefault(topic, [])
        for t in types:
            if t not in target[topic]:
                target[topic].append(t)


class RclpyGraphSource(GraphSource):
    def __init__(
        self,
        argv: Sequence[str] | None = None,
        full_every: int = 5,
        node_name: str | None = None,
    ) -> None:
        if rclpy is None:
            raise SourceError(MISSING_RCLPY)
        self.full_every = max(1, full_every)
        self._lock = threading.Lock()
        self._closed = False
        self._ticks = 0
        self._last_lists: tuple | None = None
        self._last_snapshot: GraphSnapshot | None = None

        init_kwargs = {}
        try:
            from rclpy.signals import SignalHandlerOptions

            init_kwargs["signal_handler_options"] = SignalHandlerOptions.NO
        except ImportError:  # pragma: no cover - older rclpy
            pass
        try:
            rclpy.init(args=list(argv) if argv else None, **init_kwargs)
        except Exception as exc:  # noqa: BLE001
            raise SourceError(f"rclpy.init failed: {exc}") from exc

        node_kwargs = {}
        params = inspect.signature(Node.__init__).parameters
        if "enable_rosout" in params:
            node_kwargs["enable_rosout"] = False
        if "start_parameter_services" in params:
            node_kwargs["start_parameter_services"] = False
        name = node_name or f"_rosgraph_tui_{os.getpid()}"
        try:
            self._node = rclpy.create_node(name, **node_kwargs)
        except Exception as exc:  # noqa: BLE001
            rclpy.try_shutdown()
            raise SourceError(f"could not create the introspection node: {exc}") from exc

    # --- GraphSource --------------------------------------------------------

    def describe(self) -> str:
        try:
            rmw = rclpy.utilities.get_rmw_implementation_identifier()
        except Exception:  # noqa: BLE001
            rmw = "rmw"
        return f"ROS 2 domain {os.environ.get('ROS_DOMAIN_ID', '0')} ({rmw})"

    def snapshot(self, full: bool = True) -> GraphSnapshot:
        with self._lock:
            if self._closed:
                raise SourceError("source is closed")
            started = time.perf_counter()
            nodes = list(self._node.get_node_names_and_namespaces())
            topics = [(t, list(ty)) for t, ty in self._node.get_topic_names_and_types()]
            lists_key = (
                tuple(sorted(nodes)),
                tuple((t, tuple(sorted(ty))) for t, ty in sorted(topics)),
            )
            self._ticks += 1
            last = self._last_snapshot
            if (
                not full
                and last is not None
                and lists_key == self._last_lists
                and self._ticks % self.full_every != 0
            ):
                return last

            raw = RawGraph(nodes=nodes, topics=topics)
            pubs: dict[str, dict[str, list[str]]] = {}
            subs: dict[str, dict[str, list[str]]] = {}
            calls = 0
            for name, namespace in sorted(set(nodes)):
                fqn = join_fqn(namespace, name)
                try:
                    node_pubs = self._node.get_publisher_names_and_types_by_node(name, namespace)
                    node_subs = self._node.get_subscriber_names_and_types_by_node(name, namespace)
                except Exception:  # noqa: BLE001 - node vanished mid-poll (NodeNameNonExistentError)
                    continue
                _merge(pubs.setdefault(fqn, {}), node_pubs)
                _merge(subs.setdefault(fqn, {}), node_subs)
                calls += 2
                if calls % YIELD_EVERY == 0:
                    time.sleep(0)
            raw.node_pubs = {n: list(v.items()) for n, v in pubs.items()}
            raw.node_subs = {n: list(v.items()) for n, v in subs.items()}

            poll_ms = (time.perf_counter() - started) * 1000.0
            digest = raw.digest()
            if last is not None and last.digest == digest:
                snapshot = GraphSnapshot(last.entities, time.time(), digest, poll_ms)
            else:
                snapshot = build_snapshot(raw, poll_ms=poll_ms)
            self._last_lists = lists_key
            self._last_snapshot = snapshot
            return snapshot

    def topic_endpoints(self, topic: str) -> list[Endpoint]:
        with self._lock:
            if self._closed:
                raise SourceError("source is closed")
            result: list[Endpoint] = []
            for is_publisher, getter in (
                (True, self._node.get_publishers_info_by_topic),
                (False, self._node.get_subscriptions_info_by_topic),
            ):
                for info in getter(topic):
                    node = EntityRef(Kind.NODE, join_fqn(info.node_namespace, info.node_name))
                    qos = _qos_summary(info.qos_profile)
                    result.append(Endpoint(node, is_publisher, info.topic_type, qos))
            return result

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._node.destroy_node()
            finally:
                try:
                    if rclpy.ok():
                        rclpy.shutdown()
                except Exception:  # noqa: BLE001
                    pass
