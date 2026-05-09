"""Tool registration for Amazing ROS 2 MCP Server."""

from typing import Annotated

import anyio
from fastmcp import FastMCP

from .topics import register_topic_tools
from .services import register_service_tools
from .actions import register_action_tools
from .nodes import register_node_tools
from .params import register_param_tools

from ..core.msg_convert import safe_json_dumps


def register_all_tools(mcp: FastMCP) -> None:
    """Register all tool modules."""
    register_topic_tools(mcp)
    register_service_tools(mcp)
    register_action_tools(mcp)
    register_node_tools(mcp)
    register_param_tools(mcp)

    # Optional: Image tools (needs sensor_msgs + cv2/numpy at runtime)
    try:
        from .image import register_image_tools
        register_image_tools(mcp)
    except ImportError:
        pass

    # Optional: Nav2 plugin
    try:
        from .nav2 import register_nav2_tools
        register_nav2_tools(mcp)
    except ImportError:
        pass  # nav2_simple_commander not installed

    # Utility: detect ROS version
    @mcp.tool(
        name="detect_ros_version",
        description="Detect the installed ROS 2 distribution and version.",
        tags={"ros", "version", "utility"},
        annotations={"title": "Detect ROS Version", "readOnlyHint": True},
    )
    async def detect_ros_version() -> str:
        """Return ROS distro, Python version, and ament info."""
        def _sync():
            import os, sys, platform
            distro = os.environ.get("ROS_DISTRO", "unknown")
            domain_id = os.environ.get("ROS_DOMAIN_ID", "0")
            rmw = os.environ.get("RMW_IMPLEMENTATION", "default")
            return safe_json_dumps({
                "ros_distro": distro,
                "ros_domain_id": domain_id,
                "rmw_implementation": rmw,
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
            })
        return await anyio.to_thread.run_sync(_sync)
