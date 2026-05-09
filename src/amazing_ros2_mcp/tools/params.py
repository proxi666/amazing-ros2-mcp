"""Parameter tools — list, get, set. Native rclpy service calls."""

from typing import Annotated

import anyio
from fastmcp import FastMCP

from ..core.node import get_ros2_node
from ..core.msg_convert import safe_json_dumps


def register_param_tools(mcp: FastMCP) -> None:
    """Register parameter-related MCP tools."""

    @mcp.tool(
        name="list_parameters",
        description=(
            "List all parameters of a specific ROS 2 node.\n"
            "Example: list_parameters('/teleop_keyboard')"
        ),
        tags={"parameters", "list", "config"},
        annotations={"title": "List Parameters", "readOnlyHint": True},
    )
    async def list_parameters(
        node_name: Annotated[str, "Full node name (e.g. '/teleop_keyboard')"],
    ) -> str:
        """List all parameter names of target node."""
        def _sync():
            node = get_ros2_node()
            result = node.list_parameters_of_node(node_name)
            return safe_json_dumps({
                "node": node_name,
                "parameters": result,
            })
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="get_parameters",
        description=(
            "Get parameter values from a ROS 2 node.\n"
            "Example: get_parameters('/amcl', ['robot_model_type'])"
        ),
        tags={"parameters", "get", "read", "config"},
        annotations={"title": "Get Parameters", "readOnlyHint": True},
    )
    async def get_parameters(
        node_name: Annotated[str, "Full node name"],
        param_names: Annotated[list, "List of parameter names to get"],
    ) -> str:
        """Get specific parameter values."""
        def _sync():
            node = get_ros2_node()
            result = node.get_parameters_from_node(node_name, param_names)
            return safe_json_dumps({
                "node": node_name,
                "parameters": result,
            })
        return await anyio.to_thread.run_sync(_sync)
