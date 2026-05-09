"""Exception hierarchy for Amazing ROS 2 MCP Server.

Adapted from nav2_mcp_server. Generalized error codes for all ROS 2 operations.
"""

from enum import Enum
from typing import Optional


class ErrorCode(Enum):
    """Error codes for structured error reporting."""

    UNKNOWN = 0
    ROS_ERROR = 1
    TIMEOUT = 2
    INVALID_PARAMETERS = 3
    # Navigation-specific
    NAVIGATION_FAILED = 10
    NAVIGATION_CANCELED = 11
    TRANSFORM_UNAVAILABLE = 12
    NAV2_NOT_ACTIVE = 13
    INVALID_WAYPOINTS = 14
    # Topic/service/action
    TOPIC_NOT_FOUND = 20
    SERVICE_NOT_FOUND = 21
    ACTION_NOT_FOUND = 22
    MESSAGE_TYPE_ERROR = 23


class MCPError(Exception):
    """Base exception for all Amazing ROS 2 MCP errors."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.UNKNOWN,
        details: Optional[dict] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "code": self.code.name,
            "details": self.details,
        }


class ROSError(MCPError):
    """ROS 2 operation failed."""

    def __init__(self, message: str, cause: Optional[Exception] = None, **kwargs):
        details = kwargs.pop("details", {})
        if cause:
            details["cause_type"] = type(cause).__name__
            details["cause_msg"] = str(cause)
        super().__init__(message, ErrorCode.ROS_ERROR, details)


class TimeoutError(MCPError):
    """Operation timed out."""

    def __init__(self, message: str, timeout_sec: Optional[float] = None, **kwargs):
        details = kwargs.pop("details", {})
        if timeout_sec is not None:
            details["timeout_sec"] = timeout_sec
        super().__init__(message, ErrorCode.TIMEOUT, details)


class NavigationError(MCPError):
    """Navigation operation failed."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.NAVIGATION_FAILED,
        details: Optional[dict] = None,
    ):
        super().__init__(message, code, details)


class TransformError(MCPError):
    """TF transform lookup failed."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, ErrorCode.TRANSFORM_UNAVAILABLE, details)
