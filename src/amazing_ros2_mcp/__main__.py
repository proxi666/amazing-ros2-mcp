"""Entry point for `python -m amazing_ros2_mcp`."""

import asyncio
import sys

from .server import run_server


def main():
    """Run the Amazing ROS 2 MCP server."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"Fatal: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
