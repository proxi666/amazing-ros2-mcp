"""Nav2 navigation plugin — optional, loads only if nav2_simple_commander available.

Adapted from ajtudela/nav2_mcp_server with simplified integration.
"""

import math
import json
from typing import Annotated, Optional

import anyio
from fastmcp import Context, FastMCP

from ..config import get_config
from ..core.msg_convert import safe_json_dumps
from ..exceptions import NavigationError, ErrorCode


def register_nav2_tools(mcp: FastMCP) -> None:
    """Register Nav2 navigation tools."""
    from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
    from geometry_msgs.msg import PoseStamped

    _navigator: Optional[BasicNavigator] = None

    def _get_nav() -> BasicNavigator:
        nonlocal _navigator
        if _navigator is None:
            _navigator = BasicNavigator()
        return _navigator

    def _make_pose(x: float, y: float, yaw: float = 0.0) -> PoseStamped:
        config = get_config()
        pose = PoseStamped()
        pose.header.frame_id = config.ros.map_frame
        pose.header.stamp = _get_nav().get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.orientation.w = math.cos(yaw / 2.0)
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        return pose

    @mcp.tool(
        name="navigate_to_pose",
        description=(
            "Navigate robot to a specific pose in the map frame.\n"
            "Example: navigate_to_pose(2.0, 3.0, 1.57)"
        ),
        tags={"navigate", "go to", "move to", "position"},
        annotations={"title": "Navigate To Pose", "readOnlyHint": False,
                      "destructiveHint": True},
    )
    async def navigate_to_pose(
        x: Annotated[float, "X coordinate in map frame"],
        y: Annotated[float, "Y coordinate in map frame"],
        yaw: Annotated[float, "Orientation in radians"] = 0.0,
        timeout: Annotated[float, "Timeout in seconds (0 = wait forever)"] = 60.0,
    ) -> str:
        """Navigate to pose using Nav2."""
        def _sync():
            import time
            nav = _get_nav()
            goal = _make_pose(x, y, yaw)
            nav.goToPose(goal)
            
            start_time = time.time()
            while not nav.isTaskComplete():
                time.sleep(0.1)
                if timeout > 0 and (time.time() - start_time) > timeout:
                    nav.cancelTask()
                    return safe_json_dumps({
                        "success": False,
                        "error": f"Navigation timed out after {timeout}s",
                    })
                    
            result = nav.getResult()
            if result == TaskResult.SUCCEEDED:
                return safe_json_dumps({
                    "success": True,
                    "message": f"Navigated to ({x:.2f}, {y:.2f}, {yaw:.2f})",
                })
            return safe_json_dumps({
                "success": False,
                "error": f"Navigation failed: {result}",
            })
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="follow_waypoints",
        description=(
            "Navigate through a sequence of waypoints.\n"
            "Example: follow_waypoints('[[0,0],[2,0],[2,2]]')"
        ),
        tags={"waypoints", "patrol", "sequence"},
        annotations={"title": "Follow Waypoints", "readOnlyHint": False,
                      "destructiveHint": True},
    )
    async def follow_waypoints(
        waypoints: Annotated[str, "JSON string [[x1,y1], [x2,y2], ...]"],
        timeout: Annotated[float, "Timeout in seconds (0 = wait forever)"] = 120.0,
    ) -> str:
        """Follow waypoints in order."""
        def _sync():
            import time
            data = json.loads(waypoints)
            poses = [_make_pose(wp[0], wp[1]) for wp in data]
            nav = _get_nav()
            nav.followWaypoints(poses)
            
            start_time = time.time()
            while not nav.isTaskComplete():
                time.sleep(0.1)
                if timeout > 0 and (time.time() - start_time) > timeout:
                    nav.cancelTask()
                    return safe_json_dumps({
                        "success": False,
                        "error": f"Waypoint following timed out after {timeout}s",
                    })
                    
            result = nav.getResult()
            if result == TaskResult.SUCCEEDED:
                return safe_json_dumps({
                    "success": True,
                    "message": f"Completed {len(poses)} waypoints",
                })
            return safe_json_dumps({
                "success": False,
                "error": f"Waypoint following failed: {result}",
            })
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="spin_robot",
        description="Spin the robot in place by a specified angle in radians.",
        tags={"spin", "rotate", "turn"},
        annotations={"title": "Spin Robot", "readOnlyHint": False},
    )
    async def spin_robot(
        angle: Annotated[float, "Angle in radians (positive=CCW)"],
        timeout: Annotated[float, "Timeout in seconds (0 = wait forever)"] = 30.0,
    ) -> str:
        """Spin robot in place."""
        def _sync():
            import time
            nav = _get_nav()
            nav.spin(angle)
            
            start_time = time.time()
            while not nav.isTaskComplete():
                time.sleep(0.1)
                if timeout > 0 and (time.time() - start_time) > timeout:
                    nav.cancelTask()
                    return safe_json_dumps({
                        "success": False,
                        "error": f"Spin timed out after {timeout}s",
                    })
                    
            result = nav.getResult()
            if result == TaskResult.SUCCEEDED:
                return safe_json_dumps({
                    "success": True,
                    "message": f"Spun {angle:.2f} radians",
                })
            return safe_json_dumps({"success": False, "error": str(result)})
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="cancel_navigation",
        description="Cancel the current navigation task.",
        tags={"cancel", "stop", "abort"},
        annotations={"title": "Cancel Navigation", "readOnlyHint": False},
    )
    async def cancel_navigation() -> str:
        """Cancel active navigation."""
        def _sync():
            nav = _get_nav()
            if nav.isTaskComplete():
                return safe_json_dumps({"message": "No active task to cancel"})
            nav.cancelTask()
            return safe_json_dumps({"message": "Navigation cancelled"})
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="clear_costmaps",
        description="Clear navigation costmaps ('global', 'local', or 'all').",
        tags={"costmap", "clear", "reset"},
        annotations={"title": "Clear Costmaps", "readOnlyHint": False},
    )
    async def clear_costmaps(
        costmap_type: Annotated[str, "'global', 'local', or 'all'"] = "all",
    ) -> str:
        """Clear costmaps."""
        def _sync():
            nav = _get_nav()
            if costmap_type == "global":
                nav.clearGlobalCostmap()
            elif costmap_type == "local":
                nav.clearLocalCostmap()
            else:
                nav.clearAllCostmaps()
            return safe_json_dumps({
                "success": True,
                "message": f"{costmap_type} costmap(s) cleared",
            })
        return await anyio.to_thread.run_sync(_sync)
