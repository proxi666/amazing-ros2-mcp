"""Node introspection tools. Native rclpy."""

from typing import Annotated

import anyio
from fastmcp import FastMCP

from ..core.node import get_ros2_node
from ..core.msg_convert import safe_json_dumps


def register_node_tools(mcp: FastMCP) -> None:
    """Register node introspection MCP tools."""

    @mcp.tool(
        name="list_nodes",
        description="List all active ROS 2 nodes with their namespaces.",
        tags={"nodes", "list", "introspection"},
        annotations={"title": "List Nodes", "readOnlyHint": True},
    )
    async def list_nodes() -> str:
        """Return all nodes in the ROS graph."""
        def _sync():
            node = get_ros2_node()
            nodes = node.get_node_names_and_namespaces()
            return safe_json_dumps({
                "nodes": [
                    {"name": name, "namespace": ns}
                    for name, ns in nodes
                ],
                "count": len(nodes),
            })
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="get_node_info",
        description=(
            "Get detailed info about a specific ROS 2 node — "
            "publishers, subscribers, services, clients."
        ),
        tags={"node", "info", "details", "publishers", "subscribers"},
        annotations={"title": "Get Node Info", "readOnlyHint": True},
    )
    async def get_node_info(
        node_name: Annotated[str, "Node name (e.g. 'teleop_keyboard')"],
        namespace: Annotated[str, "Node namespace (e.g. '/')"] = "/",
    ) -> str:
        """Get publishers, subscribers, services of a node."""
        def _sync():
            ros_node = get_ros2_node()
            n = ros_node.node

            pubs = n.get_publisher_names_and_types_by_node(node_name, namespace)
            subs = n.get_subscriber_names_and_types_by_node(node_name, namespace)
            srvs = n.get_service_names_and_types_by_node(node_name, namespace)
            clients = n.get_client_names_and_types_by_node(node_name, namespace)

            return safe_json_dumps({
                "node": node_name,
                "namespace": namespace,
                "publishers": [{"topic": t, "types": ts} for t, ts in pubs],
                "subscribers": [{"topic": t, "types": ts} for t, ts in subs],
                "services": [{"name": s, "types": ts} for s, ts in srvs],
                "clients": [{"name": c, "types": ts} for c, ts in clients],
            })
        return await anyio.to_thread.run_sync(_sync)
