"""Topic tools — list, subscribe, publish. Native rclpy."""

from typing import Annotated, Optional

import anyio
from fastmcp import Context, FastMCP

from ..core.node import get_ros2_node
from ..core.msg_convert import safe_json_dumps


def register_topic_tools(mcp: FastMCP) -> None:
    """Register topic-related MCP tools."""

    @mcp.tool(
        name="list_topics",
        description="List all active ROS 2 topics with their message types.",
        tags={"topics", "list", "introspection"},
        annotations={"title": "List Topics", "readOnlyHint": True},
    )
    async def list_topics() -> str:
        """Return all topics and types as JSON."""
        def _sync():
            node = get_ros2_node()
            topics = node.get_topic_names_and_types()
            return safe_json_dumps({
                "topics": [
                    {"name": name, "types": types}
                    for name, types in topics
                ],
                "count": len(topics),
            })
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="get_topic_message",
        description=(
            "Subscribe to a topic and get one message. "
            "Returns the message as JSON.\n"
            "Example: get_topic_message('/scan', 'sensor_msgs/msg/LaserScan')"
        ),
        tags={"topic", "subscribe", "read", "message"},
        annotations={"title": "Get Topic Message", "readOnlyHint": True},
    )
    async def get_topic_message(
        topic: Annotated[str, "Topic name (e.g. '/scan')"],
        msg_type: Annotated[str, "Message type (e.g. 'sensor_msgs/msg/LaserScan')"],
        timeout: Annotated[float, "Timeout in seconds"] = 5.0,
    ) -> str:
        """Subscribe once, return message as dict."""
        def _sync():
            node = get_ros2_node()
            data = node.subscribe_once(topic, msg_type, timeout_sec=timeout)
            return safe_json_dumps({"topic": topic, "type": msg_type, "data": data})
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="publish_message",
        description=(
            "Publish a message to a ROS 2 topic.\n"
            "Example: publish_message('/cmd_vel', 'geometry_msgs/msg/Twist', "
            "{'linear': {'x': 0.5}, 'angular': {'z': 0.1}})"
        ),
        tags={"topic", "publish", "send", "write"},
        annotations={"title": "Publish Message", "readOnlyHint": False,
                      "destructiveHint": True},
    )
    async def publish_message(
        topic: Annotated[str, "Topic name"],
        msg_type: Annotated[str, "Message type string"],
        data: Annotated[dict, "Message data as dict"],
    ) -> str:
        """Publish a single message."""
        def _sync():
            node = get_ros2_node()
            result = node.publish_message(topic, msg_type, data)
            return safe_json_dumps({"success": True, "message": result})
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="get_topic_details",
        description="Get detailed info about a topic including publishers and subscribers.",
        tags={"topics", "info", "details", "introspection"},
        annotations={"title": "Get Topic Details", "readOnlyHint": True},
    )
    async def get_topic_details(
        topic: Annotated[str, "Topic name (e.g. '/scan')"]
    ) -> str:
        """Return topic publishers, subscribers, and types."""
        def _sync():
            ros_node = get_ros2_node().node
            pubs = ros_node.get_publishers_info_by_topic(topic)
            subs = ros_node.get_subscriptions_info_by_topic(topic)
            
            # Find the type by checking the topic list
            topic_type = "unknown"
            for name, types in ros_node.get_topic_names_and_types():
                if name == topic and types:
                    topic_type = types[0]
                    break
                    
            return safe_json_dumps({
                "topic": topic,
                "type": topic_type,
                "publisher_count": len(pubs),
                "subscriber_count": len(subs),
                "publishers": [{"node_name": p.node_name, "node_namespace": p.node_namespace, "topic_type": p.topic_type} for p in pubs],
                "subscribers": [{"node_name": s.node_name, "node_namespace": s.node_namespace, "topic_type": s.topic_type} for s in subs],
            })
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="get_message_details",
        description="Get the fields and types of a specific ROS 2 message.",
        tags={"message", "type", "details", "introspection"},
        annotations={"title": "Get Message Details", "readOnlyHint": True},
    )
    async def get_message_details(
        msg_type_str: Annotated[str, "Message type (e.g. 'geometry_msgs/msg/Twist')"]
    ) -> str:
        """Return the fields and layout of a ROS 2 message type."""
        def _sync():
            node = get_ros2_node()
            try:
                msg_class = node._import_message_type(msg_type_str)
                fields = {}
                if hasattr(msg_class, "get_fields_and_field_types"):
                    fields = msg_class.get_fields_and_field_types()
                elif hasattr(msg_class, "_fields_and_field_types"):
                    fields = msg_class._fields_and_field_types
                    
                return safe_json_dumps({
                    "message_type": msg_type_str,
                    "fields": fields,
                    "field_count": len(fields)
                })
            except Exception as e:
                return safe_json_dumps({"error": str(e)})
        return await anyio.to_thread.run_sync(_sync)
