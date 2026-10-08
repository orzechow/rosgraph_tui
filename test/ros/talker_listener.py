"""Two nodes in one process, used by the integration test.

``/talker`` publishes ``/chatter`` (transient-local) and ``/listener``
subscribes to it.  Runs until killed.
"""

import sys

import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String


def main() -> None:
    suffix = sys.argv[1] if len(sys.argv) > 1 else ""
    rclpy.init()
    qos = QoSProfile(
        depth=10, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL
    )
    talker = rclpy.create_node("talker" + suffix, namespace="/it")
    listener = rclpy.create_node("listener" + suffix, namespace="/it")
    publisher = talker.create_publisher(String, "/it/chatter", qos)
    listener.create_subscription(String, "/it/chatter", lambda _msg: None, qos)
    talker.create_timer(0.5, lambda: publisher.publish(String(data="hi")))
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(talker)
    executor.add_node(listener)
    print("ready", flush=True)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
