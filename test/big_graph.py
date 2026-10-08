"""Deterministic synthetic graph at Autoware scale, for perf tests and benchmarks."""

from __future__ import annotations

import random

from rosgraph_tui.model import RawGraph

NAMESPACES = [
    "/sensing", "/perception", "/planning", "/control", "/localization", "/map", "/system", "/vehicle"
]
MSG_TYPES = [
    "sensor_msgs/msg/PointCloud2",
    "sensor_msgs/msg/Image",
    "geometry_msgs/msg/PoseStamped",
    "autoware_msgs/msg/Trajectory",
    "std_msgs/msg/Float32",
    "diagnostic_msgs/msg/DiagnosticArray",
]


def make_big_raw(nodes: int = 300, topics: int = 2000, edges: int = 8000, seed: int = 7) -> RawGraph:
    rng = random.Random(seed)
    raw = RawGraph()
    node_fqns = []
    for i in range(nodes):
        ns = rng.choice(NAMESPACES) + (f"/sub{i % 7}" if i % 3 else "")
        name = f"node_{i:03d}_{rng.choice(['driver', 'filter', 'fusion', 'planner', 'monitor'])}"
        raw.nodes.append((name, ns))
        node_fqns.append(f"{ns}/{name}")
    topic_names = []
    for i in range(topics):
        ns = rng.choice(NAMESPACES)
        name = f"{ns}/{rng.choice(['lidar', 'camera', 'objects', 'path', 'status', 'debug'])}/topic_{i:04d}"
        raw.topics.append((name, [rng.choice(MSG_TYPES)]))
        topic_names.append(name)
    types = dict(raw.topics)
    for _ in range(edges):
        node = rng.choice(node_fqns)
        topic = rng.choice(topic_names)
        target = raw.node_pubs if rng.random() < 0.4 else raw.node_subs
        target.setdefault(node, []).append((topic, list(types[topic])))
    # a few hidden ones
    raw.nodes.append(("_ros2cli_daemon_0", "/"))
    raw.topics.append(("/_internal/heartbeat", ["std_msgs/msg/Empty"]))
    return raw
