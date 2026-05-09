"""Action tools — list, send goal, cancel. Native rclpy."""

from typing import Annotated

import anyio
from fastmcp import FastMCP

from ..core.node import get_ros2_node
from ..core.msg_convert import safe_json_dumps


def register_action_tools(mcp: FastMCP) -> None:
    """Register action-related MCP tools."""

    @mcp.tool(
        name="list_actions",
        description="List all available ROS 2 action servers.",
        tags={"actions", "list", "introspection"},
        annotations={"title": "List Actions", "readOnlyHint": True},
    )
    async def list_actions() -> str:
        """Return all action servers discovered via topic naming convention."""
        def _sync():
            node = get_ros2_node()
            topics = node.get_topic_names_and_types()
            # Action servers expose /_action/status topics
            actions = set()
            for name, _types in topics:
                if name.endswith("/_action/status"):
                    action_name = name.rsplit("/_action/status", 1)[0]
                    actions.add(action_name)
            return safe_json_dumps({
                "actions": sorted(actions),
                "count": len(actions),
            })
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="send_action_goal",
        description=(
            "Send a goal to a ROS 2 action server.\n"
            "Example: send_action_goal('/navigate_to_pose', "
            "'nav2_msgs/action/NavigateToPose', {'pose': {...}})"
        ),
        tags={"action", "goal", "send", "navigate"},
        annotations={"title": "Send Action Goal", "readOnlyHint": False,
                      "destructiveHint": True},
    )
    async def send_action_goal(
        action_name: Annotated[str, "Action server name"],
        action_type: Annotated[str, "Action type (e.g. 'nav2_msgs/action/NavigateToPose')"],
        goal: Annotated[dict, "Goal data as dict"],
        timeout: Annotated[float, "Timeout waiting for result in seconds"] = 30.0,
    ) -> str:
        """Send goal and wait for result."""
        def _sync():
            import importlib
            import threading

            node = get_ros2_node()
            # Import action type
            parts = action_type.replace("/", ".").rsplit(".", 2)
            module = importlib.import_module(f"{parts[0]}.{parts[1]}")
            action_class = getattr(module, parts[2])

            from rclpy.action import ActionClient

            client = ActionClient(node.node, action_class, action_name)
            if not client.wait_for_server(timeout_sec=10.0):
                client.destroy()
                return safe_json_dumps({
                    "action": action_name,
                    "success": False,
                    "error": "Action server not available",
                })

            goal_msg = node._dict_to_msg(action_class.Goal, goal)
            future = client.send_goal_async(goal_msg)

            # Wait for goal acceptance
            event = threading.Event()
            future.add_done_callback(lambda f: event.set())
            if not event.wait(timeout=10.0):
                client.destroy()
                return safe_json_dumps({
                    "action": action_name,
                    "success": False,
                    "error": "Goal sending timed out",
                })
                
            goal_handle = future.result()
            if not goal_handle or not goal_handle.accepted:
                client.destroy()
                return safe_json_dumps({
                    "action": action_name,
                    "success": False,
                    "error": "Goal rejected",
                })

            # Wait for result
            result_future = goal_handle.get_result_async()
            res_event = threading.Event()
            result_future.add_done_callback(lambda f: res_event.set())
            if not res_event.wait(timeout=timeout):
                client.destroy()
                return safe_json_dumps({
                    "action": action_name,
                    "success": False,
                    "error": f"Timed out after {timeout}s waiting for result",
                })
                
            result = result_future.result()
            client.destroy()

            from ..core.msg_convert import msg_to_dict
            return safe_json_dumps({
                "action": action_name,
                "success": True,
                "status": result.status,
                "result": msg_to_dict(result.result),
            })

        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="get_action_details",
        description="Get the Goal, Result, and Feedback structure of a specific ROS 2 action.",
        tags={"action", "type", "details", "introspection"},
        annotations={"title": "Get Action Details", "readOnlyHint": True},
    )
    async def get_action_details(
        action_type_str: Annotated[str, "Action type (e.g. 'nav2_msgs/action/NavigateToPose')"]
    ) -> str:
        """Return the fields of a ROS 2 action Goal, Result, and Feedback."""
        def _sync():
            node = get_ros2_node()
            try:
                import importlib
                parts = action_type_str.replace("/", ".").rsplit(".", 2)
                module = importlib.import_module(f"{parts[0]}.{parts[1]}")
                action_class = getattr(module, parts[2])
                
                goal_fields = getattr(action_class.Goal, "get_fields_and_field_types", lambda: getattr(action_class.Goal, "_fields_and_field_types", {}))()
                res_fields = getattr(action_class.Result, "get_fields_and_field_types", lambda: getattr(action_class.Result, "_fields_and_field_types", {}))()
                fb_fields = getattr(action_class.Feedback, "get_fields_and_field_types", lambda: getattr(action_class.Feedback, "_fields_and_field_types", {}))()
                
                return safe_json_dumps({
                    "action_type": action_type_str,
                    "goal": {"fields": goal_fields, "field_count": len(goal_fields)},
                    "result": {"fields": res_fields, "field_count": len(res_fields)},
                    "feedback": {"fields": fb_fields, "field_count": len(fb_fields)}
                })
            except Exception as e:
                return safe_json_dumps({"error": str(e)})
        return await anyio.to_thread.run_sync(_sync)
