"""ROS 2 Node wrapper with background spin thread.

Heart of the server. Creates single rclpy node, spins in daemon thread.
All tools call into this node for topic/service/action operations.
Pattern from kakimochi/ros2-mcp-server + nav2_mcp_server.
"""

import glob
import importlib
import json
import os
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from ..config import get_config
from ..exceptions import MCPError, ErrorCode, ROSError, TimeoutError


def _workspace_roots() -> List[str]:
    """Find ROS workspaces from env and current package location."""
    starts = []
    for key in ("AMAZING_ROS2_WORKSPACE", "ROS_WORKSPACE"):
        value = os.environ.get(key)
        if value:
            starts.append(value)
    starts.extend([os.getcwd(), os.path.dirname(__file__)])

    roots = []
    seen = set()
    for start in starts:
        current = os.path.abspath(os.path.expanduser(start))
        while True:
            if current not in seen and os.path.isdir(os.path.join(current, "install")):
                seen.add(current)
                roots.append(current)
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
    return roots


def _ensure_workspace_packages():
    """Inject workspace Python paths into sys.path.

    When launched by an MCP client (e.g. Claude Desktop) the process may not
    inherit the full PYTHONPATH that ``source install/setup.bash`` provides.
    This reads ``AMENT_PREFIX_PATH`` plus nearby workspace installs, then adds
    ``<prefix>/local/lib/python*/dist-packages`` directory that is not
    already on ``sys.path``.
    """
    prefixes = [p for p in os.environ.get("AMENT_PREFIX_PATH", "").split(":") if p]
    for root in _workspace_roots():
        install_dir = os.path.join(root, "install")
        prefixes.append(install_dir)
        prefixes.extend(
            path for path in glob.glob(os.path.join(install_dir, "*"))
            if os.path.isdir(path)
        )

    unique_prefixes = []
    seen_prefixes = set()
    for prefix in prefixes:
        prefix = os.path.abspath(os.path.expanduser(prefix))
        if prefix in seen_prefixes or not os.path.isdir(prefix):
            continue
        seen_prefixes.add(prefix)
        unique_prefixes.append(prefix)

    if unique_prefixes:
        os.environ["AMENT_PREFIX_PATH"] = ":".join(unique_prefixes)

    for prefix in unique_prefixes:
        # Match any python3.X version in the prefix
        candidates = glob.glob(
            os.path.join(prefix, "local", "lib", "python3*", "dist-packages")
        )
        # Also check the non-local variant used by some colcon setups
        candidates += glob.glob(
            os.path.join(prefix, "lib", "python3*", "dist-packages")
        )
        for path in candidates:
            if os.path.isdir(path) and path not in sys.path:
                sys.path.insert(0, path)


class ROS2Node:
    """Managed rclpy node with background spin thread."""

    def __init__(self):
        _ensure_workspace_packages()
        self._config = get_config()
        self._node: Optional[Node] = None
        self._spin_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._publishers: dict = {}

    @property
    def node(self) -> Node:
        """Get the rclpy node, initializing if needed."""
        if self._node is None:
            self._ensure_init()
        return self._node

    def _ensure_init(self):
        """Initialize rclpy and start spin thread."""
        with self._lock:
            if self._node is not None:
                return
            if not rclpy.ok():
                rclpy.init()
            cfg = self._config.ros
            self._node = Node(cfg.node_name, namespace=cfg.namespace or None)
            self._spin_thread = threading.Thread(
                target=self._spin_loop, daemon=True
            )
            self._spin_thread.start()
            self._node.get_logger().info("Amazing ROS2 MCP node started")

    def _spin_loop(self):
        """Background spin loop."""
        while rclpy.ok() and self._node is not None:
            rclpy.spin_once(self._node, timeout_sec=self._config.ros.spin_timeout_sec)

    # ---- Topic operations ----

    def get_topic_names_and_types(self) -> List[Tuple[str, List[str]]]:
        """Return list of (topic_name, [type_strings])."""
        return self.node.get_topic_names_and_types()

    def subscribe_once(self, topic: str, msg_type_str: str, timeout_sec: float = 5.0) -> dict:
        """Subscribe to topic, get one message, return as dict."""
        msg_class = self._import_message_type(msg_type_str)
        result = {"received": False, "data": None}
        event = threading.Event()

        def callback(msg):
            from .msg_convert import msg_to_dict
            result["data"] = msg_to_dict(msg)
            result["received"] = True
            event.set()

        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        sub = self.node.create_subscription(msg_class, topic, callback, qos)
        try:
            if not event.wait(timeout=timeout_sec):
                raise TimeoutError(
                    f"No message on '{topic}' within {timeout_sec}s",
                    timeout_sec=timeout_sec,
                )
            return result["data"]
        finally:
            self.node.destroy_subscription(sub)

    def publish_message(self, topic: str, msg_type_str: str, data: dict) -> str:
        """Publish a single message to a topic."""
        safety = self._config.safety

        # Block forbidden topics
        if topic in safety.blocked_topics:
            raise MCPError(
                f"Publishing to '{topic}' is blocked by safety config",
                ErrorCode.INVALID_PARAMETERS,
            )

        # Clamp cmd_vel velocities
        if topic.endswith("/cmd_vel") and isinstance(data, dict):
            lin = data.get("linear", {})
            ang = data.get("angular", {})
            if isinstance(lin, dict):
                if "x" in lin:
                    lin["x"] = max(-safety.max_linear_x, min(safety.max_linear_x, float(lin["x"])))
                if "y" in lin:
                    lin["y"] = max(-safety.max_linear_y, min(safety.max_linear_y, float(lin["y"])))
            if isinstance(ang, dict) and "z" in ang:
                ang["z"] = max(-safety.max_angular_z, min(safety.max_angular_z, float(ang["z"])))

        # Dry-run: log but do not publish
        if safety.dry_run:
            return f"[DRY RUN] Would publish to '{topic}': {data}"

        msg_class = self._import_message_type(msg_type_str)
        msg = self._dict_to_msg(msg_class, data)

        if topic not in self._publishers:
            qos = QoSProfile(depth=self._config.ros.default_qos_depth)
            self._publishers[topic] = self.node.create_publisher(msg_class, topic, qos)
            import time
            time.sleep(0.1)  # allow tiny window for DDS discovery on first creation

        self._publishers[topic].publish(msg)
        return f"Published to '{topic}'"

    # ---- Service operations ----

    def get_service_names_and_types(self) -> List[Tuple[str, List[str]]]:
        """Return list of (service_name, [type_strings])."""
        return self.node.get_service_names_and_types()

    def call_service(
        self, service_name: str, srv_type_str: str, request_data: dict,
        timeout_sec: Optional[float] = None,
    ) -> dict:
        """Call a ROS 2 service and return response as dict."""
        srv_class = self._import_message_type(srv_type_str)
        if timeout_sec is None:
            timeout_sec = self._config.ros.service_timeout_sec

        client = self.node.create_client(srv_class, service_name)
        try:
            if not client.wait_for_service(timeout_sec=timeout_sec):
                raise TimeoutError(
                    f"Service '{service_name}' not available",
                    timeout_sec=timeout_sec,
                )
            request = self._dict_to_msg(srv_class.Request, request_data)
            future = client.call_async(request)
            
            # The daemon thread is already spinning the node, so we wait for the future
            event = threading.Event()
            future.add_done_callback(lambda f: event.set())
            
            if not event.wait(timeout=timeout_sec):
                raise TimeoutError(
                    f"Service call to '{service_name}' timed out after {timeout_sec}s",
                    timeout_sec=timeout_sec
                )
                
            if future.result() is None:
                raise ROSError(f"Service call to '{service_name}' failed")
            from .msg_convert import msg_to_dict
            return msg_to_dict(future.result())
        finally:
            self.node.destroy_client(client)

    # ---- Node introspection ----

    def get_node_names_and_namespaces(self) -> List[Tuple[str, str]]:
        """Return list of (node_name, namespace)."""
        return self.node.get_node_names_and_namespaces()

    # ---- Parameter operations ----

    def get_parameters_from_node(
        self, target_node: str, param_names: List[str]
    ) -> dict:
        """Get parameters from a remote node via service call."""
        srv_name = f"{target_node}/get_parameters"
        request = {"names": param_names}
        return self.call_service(
            srv_name, "rcl_interfaces/srv/GetParameters", request
        )

    def list_parameters_of_node(self, target_node: str) -> dict:
        """List all parameters of a remote node."""
        srv_name = f"{target_node}/list_parameters"
        return self.call_service(
            srv_name, "rcl_interfaces/srv/ListParameters", {}
        )

    # ---- Helpers ----

    def _import_message_type(self, type_str: str) -> Any:
        """Import a ROS 2 message/service/action class from string.

        e.g. 'std_msgs/msg/String' → std_msgs.msg.String
        """
        _ensure_workspace_packages()
        parts = type_str.replace("/", ".").rsplit(".", 2)
        if len(parts) < 3:
            raise MCPError(
                f"Invalid type format: '{type_str}'. Expected 'pkg/msg/Type'",
                ErrorCode.MESSAGE_TYPE_ERROR,
            )
        module_path = f"{parts[0]}.{parts[1]}"
        class_name = parts[2]
        try:
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except (ImportError, AttributeError) as exc:
            raise MCPError(
                f"Cannot import '{type_str}': {exc}",
                ErrorCode.MESSAGE_TYPE_ERROR,
                {"type_str": type_str},
            )

    def _dict_to_msg(self, msg_class: Any, data: dict) -> Any:
        """Convert dict to ROS message instance."""
        if not data:
            return msg_class()
        msg = msg_class()
        for key, value in data.items():
            if hasattr(msg, key):
                field_val = getattr(msg, key)
                # Handle nested messages
                if hasattr(field_val, '__slots__') and isinstance(value, dict):
                    setattr(msg, key, self._dict_to_msg(type(field_val), value))
                else:
                    setattr(msg, key, value)
        return msg

    def destroy(self):
        """Shutdown node and spin thread."""
        with self._lock:
            if self._node:
                self._node.get_logger().info("Shutting down Amazing ROS2 MCP node")
                # Stop the spin loop from re-entering
                node_ref = self._node
                self._node = None
                
                # If we are not in the spin thread, wait for it to exit
                if self._spin_thread and threading.current_thread() != self._spin_thread:
                    self._spin_thread.join(timeout=1.0)
                    
                node_ref.destroy_node()
                
            if rclpy.ok():
                try:
                    rclpy.shutdown()
                except Exception:
                    pass


# Global singleton
_ros2_node: Optional[ROS2Node] = None


def get_ros2_node() -> ROS2Node:
    """Get or create global ROS2Node."""
    global _ros2_node
    if _ros2_node is None:
        _ros2_node = ROS2Node()
    return _ros2_node
