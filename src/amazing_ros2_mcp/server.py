"""Server — FastMCP init, tool/resource registration, lifecycle."""

import logging
import sys
from typing import Optional

from fastmcp import FastMCP

from .config import get_config
from .tools import register_all_tools
from .resources.system_info import register_resources


def create_server() -> FastMCP:
    """Create and configure the MCP server."""
    config = get_config()
    mcp = FastMCP(config.server.name)
    register_all_tools(mcp)
    register_resources(mcp)
    return mcp


async def run_server() -> None:
    """Run the Amazing ROS 2 MCP server."""
    config = get_config()

    # Setup logging
    logging.basicConfig(
        level=config.logging.level,
        format=config.logging.format,
    )
    logger = logging.getLogger("amazing_ros2_mcp")
    logger.info("Starting Amazing ROS 2 MCP Server...")

    server = create_server()

    try:
        transport = config.server.transport
        if transport == "stdio":
            logger.info("Transport: stdio")
            await server.run_async(transport="stdio")
        elif transport in ("http", "streamable-http"):
            logger.info(f"Transport: {transport} on {config.server.host}:{config.server.port}")
            await server.run_async(
                transport=transport,
                host=config.server.host,
                port=config.server.port,
            )
        else:
            raise ValueError(f"Unknown transport: {transport}")
    except KeyboardInterrupt:
        logger.info("Server interrupted")
    finally:
        # Cleanup ROS node
        try:
            from .core.node import get_ros2_node
            get_ros2_node().destroy()
        except Exception:
            pass
        logger.info("Server shutdown complete")
