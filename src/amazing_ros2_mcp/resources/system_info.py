"""MCP Resources — expose ROS 2 system info as queryable resources."""

from fastmcp import FastMCP

from ..core.node import get_ros2_node
from ..core.msg_convert import safe_json_dumps


def register_resources(mcp: FastMCP) -> None:
    """Register MCP resources for ROS 2 system introspection."""

    @mcp.resource(
        uri="ros2://system/info",
        name="ROS 2 System Info",
        description="Overview of all topics, services, nodes in the ROS 2 graph",
        mime_type="application/json",
    )
    def get_system_info() -> str:
        """Full system snapshot."""
        node = get_ros2_node()
        topics = node.get_topic_names_and_types()
        services = node.get_service_names_and_types()
        nodes = node.get_node_names_and_namespaces()

        return safe_json_dumps({
            "topics": [{"name": n, "types": t} for n, t in topics],
            "services": [{"name": n, "types": t} for n, t in services],
            "nodes": [{"name": n, "namespace": ns} for n, ns in nodes],
            "summary": {
                "topic_count": len(topics),
                "service_count": len(services),
                "node_count": len(nodes),
            },
        })

    @mcp.resource(
        uri="ros2://topics",
        name="ROS 2 Topics",
        description="All active topics with message types",
        mime_type="application/json",
    )
    def get_topics_resource() -> str:
        """Topics list."""
        node = get_ros2_node()
        topics = node.get_topic_names_and_types()
        return safe_json_dumps({
            "topics": [{"name": n, "types": t} for n, t in topics],
            "count": len(topics),
        })

    @mcp.resource(
        uri="ros2://nodes",
        name="ROS 2 Nodes",
        description="All active nodes with namespaces",
        mime_type="application/json",
    )
    def get_nodes_resource() -> str:
        """Nodes list."""
        node = get_ros2_node()
        nodes = node.get_node_names_and_namespaces()
        return safe_json_dumps({
            "nodes": [{"name": n, "namespace": ns} for n, ns in nodes],
            "count": len(nodes),
        })
