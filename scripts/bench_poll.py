#!/usr/bin/env python3
"""Measure RclpyGraphSource.snapshot() against a synthetic ROS 2 graph.

Run inside a sourced ROS 2 environment (see the Docker job in CI)::

    python3 scripts/bench_poll.py --nodes 200 --topics-per-node 10

It starts ``--nodes`` rclpy nodes in this process, each with
``--topics-per-node`` publishers and as many subscriptions, waits for
discovery, then times full polls, cheap polls and a lazy QoS fetch.
"""

from __future__ import annotations

import argparse
import statistics
import time

import rclpy
from std_msgs.msg import String

from rosgraph_tui.model import Kind
from rosgraph_tui.rclpy_source import RclpyGraphSource


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=200)
    parser.add_argument("--topics-per-node", type=int, default=10)
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()

    rclpy.init()
    nodes = []
    keep = []
    for i in range(args.nodes):
        node = rclpy.create_node(f"bench_node_{i:03d}", namespace=f"/bench/ns{i % 8}")
        for j in range(args.topics_per_node):
            pub_topic = f"/bench/topic_{(i * 7 + j) % (args.nodes * 3):04d}"
            sub_topic = f"/bench/topic_{(i * 3 + j) % (args.nodes * 3):04d}"
            keep.append(node.create_publisher(String, pub_topic, 10))
            keep.append(node.create_subscription(String, sub_topic, lambda _m: None, 10))
        nodes.append(node)

    source = RclpyGraphSource(node_name="_rosgraph_tui_bench")
    print("waiting for discovery", end="", flush=True)
    deadline = time.time() + 30
    while time.time() < deadline:
        snap = source.snapshot(full=True)
        if snap.count(Kind.NODE) >= args.nodes:
            break
        print(".", end="", flush=True)
        time.sleep(1)
    print()
    print(f"graph: {snap.count(Kind.NODE)} nodes, {snap.count(Kind.TOPIC)} topics")

    full = [source.snapshot(full=True).poll_ms for _ in range(args.rounds)]
    cheap = []
    for _ in range(args.rounds):
        start = time.perf_counter()
        source.snapshot(full=False)
        cheap.append((time.perf_counter() - start) * 1000)
    topic = snap.names(Kind.TOPIC)[0]
    start = time.perf_counter()
    endpoints = source.topic_endpoints(topic)
    qos_ms = (time.perf_counter() - start) * 1000

    for label, values in (("full poll: ", full), ("cheap poll:", cheap)):
        median, lo, hi = statistics.median(values), min(values), max(values)
        print(f"{label} median {median:.1f} ms  (min {lo:.1f}, max {hi:.1f})")
    print(f"lazy QoS for {topic}: {qos_ms:.1f} ms, {len(endpoints)} endpoints")

    source.close()
    for node in nodes:
        node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
