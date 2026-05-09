"""Service tools — list, call. Native rclpy."""

from typing import Annotated, Optional

import anyio
from fastmcp import FastMCP

from ..core.node import get_ros2_node
from ..core.msg_convert import safe_json_dumps


def register_service_tools(mcp: FastMCP) -> None:
    """Register service-related MCP tools."""

    @mcp.tool(
        name="list_services",
        description="List all active ROS 2 services with their types.",
        tags={"services", "list", "introspection"},
        annotations={"title": "List Services", "readOnlyHint": True},
    )
    async def list_services() -> str:
        """Return all services and types."""
        def _sync():
            node = get_ros2_node()
            services = node.get_service_names_and_types()
            return safe_json_dumps({
                "services": [
                    {"name": name, "types": types}
                    for name, types in services
                ],
                "count": len(services),
            })
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="call_service",
        description=(
            "Call a ROS 2 service with request data.\n"
            "Example: call_service('/rosapi/topics', 'rosapi/srv/Topics', {})"
        ),
        tags={"service", "call", "request"},
        annotations={"title": "Call Service", "readOnlyHint": False,
                      "destructiveHint": True},
    )
    async def call_service(
        service_name: Annotated[str, "Service name (e.g. '/spawn')"],
        service_type: Annotated[str, "Service type (e.g. 'turtlesim/srv/Spawn')"],
        request: Annotated[dict, "Request data as dict"] = {},
        timeout: Annotated[float, "Timeout in seconds"] = 5.0,
    ) -> str:
        """Call service, return response as JSON."""
        def _sync():
            node = get_ros2_node()
            resp = node.call_service(service_name, service_type, request, timeout)
            return safe_json_dumps({
                "service": service_name,
                "success": True,
                "response": resp,
            })
        return await anyio.to_thread.run_sync(_sync)

    @mcp.tool(
        name="get_service_details",
        description="Get the request and response structure of a specific ROS 2 service.",
        tags={"service", "type", "details", "introspection"},
        annotations={"title": "Get Service Details", "readOnlyHint": True},
    )
    async def get_service_details(
        srv_type_str: Annotated[str, "Service type (e.g. 'std_srvs/srv/SetBool')"]
    ) -> str:
        """Return the fields of a ROS 2 service Request and Response."""
        def _sync():
            node = get_ros2_node()
            try:
                srv_class = node._import_message_type(srv_type_str)
                req_fields = {}
                res_fields = {}
                
                if hasattr(srv_class.Request, "get_fields_and_field_types"):
                    req_fields = srv_class.Request.get_fields_and_field_types()
                elif hasattr(srv_class.Request, "_fields_and_field_types"):
                    req_fields = srv_class.Request._fields_and_field_types
                    
                if hasattr(srv_class.Response, "get_fields_and_field_types"):
                    res_fields = srv_class.Response.get_fields_and_field_types()
                elif hasattr(srv_class.Response, "_fields_and_field_types"):
                    res_fields = srv_class.Response._fields_and_field_types
                    
                return safe_json_dumps({
                    "service_type": srv_type_str,
                    "request": {"fields": req_fields, "field_count": len(req_fields)},
                    "response": {"fields": res_fields, "field_count": len(res_fields)}
                })
            except Exception as e:
                return safe_json_dumps({"error": str(e)})
        return await anyio.to_thread.run_sync(_sync)
