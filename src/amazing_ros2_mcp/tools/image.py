"""Image tools — subscribe to camera topics, return base64 or save to disk."""

import base64
import os
from typing import Annotated, Optional

import anyio
from fastmcp import FastMCP

from ..core.node import get_ros2_node
from ..core.msg_convert import safe_json_dumps


def register_image_tools(mcp: FastMCP) -> None:
    """Register image-related MCP tools."""

    @mcp.tool(
        name="get_camera_image",
        description=(
            "Subscribe to a ROS 2 image topic and return the image.\n"
            "By default returns base64-encoded JPEG. Optionally saves to disk.\n"
            "Example: get_camera_image('/camera/image_raw')"
        ),
        tags={"camera", "image", "vision", "subscribe"},
        annotations={"title": "Get Camera Image", "readOnlyHint": True},
    )
    async def get_camera_image(
        topic: Annotated[str, "Image topic (e.g. '/camera/image_raw')"],
        save_path: Annotated[Optional[str], "If set, save JPEG to this path"] = None,
        timeout: Annotated[float, "Timeout in seconds"] = 5.0,
    ) -> str:
        """Subscribe once to an image topic, compress, return base64."""
        def _sync():
            import threading
            node = get_ros2_node()

            # Import sensor_msgs
            try:
                from sensor_msgs.msg import Image, CompressedImage
            except ImportError:
                return safe_json_dumps({
                    "error": "sensor_msgs not found. Install ros-humble-sensor-msgs."
                })

            result = {"received": False, "data": None}
            event = threading.Event()

            def callback(msg):
                result["data"] = msg
                result["received"] = True
                event.set()

            from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
            qos = QoSProfile(
                depth=1,
                reliability=ReliabilityPolicy.BEST_EFFORT,
                durability=DurabilityPolicy.VOLATILE,
            )

            # Try CompressedImage first for efficiency, fall back to raw Image
            sub = node.node.create_subscription(Image, topic, callback, qos)
            try:
                if not event.wait(timeout=timeout):
                    return safe_json_dumps({
                        "error": f"No image on '{topic}' within {timeout}s"
                    })

                msg = result["data"]
                jpeg_bytes = _raw_to_jpeg(msg)
                if jpeg_bytes is None:
                    return safe_json_dumps({
                        "error": "Failed to encode image. cv2/numpy may not be installed."
                    })

                if save_path:
                    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
                    with open(save_path, "wb") as f:
                        f.write(jpeg_bytes)

                b64 = base64.b64encode(jpeg_bytes).decode("ascii")
                return safe_json_dumps({
                    "topic": topic,
                    "encoding": msg.encoding,
                    "width": msg.width,
                    "height": msg.height,
                    "format": "jpeg",
                    "base64_length": len(b64),
                    "saved_to": save_path,
                    "base64": b64[:200] + "..." if len(b64) > 200 else b64,
                })
            finally:
                node.node.destroy_subscription(sub)

        return await anyio.to_thread.run_sync(_sync)


def _raw_to_jpeg(msg) -> Optional[bytes]:
    """Convert a sensor_msgs/Image to JPEG bytes."""
    try:
        import numpy as np
        import cv2
    except ImportError:
        return None

    # Determine dtype and channels from encoding
    encoding = msg.encoding.lower()
    h, w = msg.height, msg.width

    if encoding in ("rgb8",):
        arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(h, w, 3)
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    elif encoding in ("bgr8",):
        arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(h, w, 3)
    elif encoding in ("mono8",):
        arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(h, w)
    elif encoding in ("rgba8",):
        arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(h, w, 4)
        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    elif encoding in ("bgra8",):
        arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(h, w, 4)
        arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
    elif encoding in ("16uc1", "mono16"):
        arr = np.frombuffer(msg.data, dtype=np.uint16).reshape(h, w)
        arr = (arr / 256).astype(np.uint8)
    else:
        # Best-effort: try as 3-channel uint8
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(h, w, 3)
        except ValueError:
            return None

    success, jpeg = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return jpeg.tobytes() if success else None
