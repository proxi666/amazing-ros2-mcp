"""Configuration for Amazing ROS 2 MCP Server.

Dataclass-based config with environment variable overrides and validation.
Adapted from nav2_mcp_server's config pattern.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from dotenv import load_dotenv


@dataclass
class ServerConfig:
    """MCP server settings."""

    name: str = "amazing-ros2-mcp"
    transport: str = "stdio"
    host: str = "0.0.0.0"
    port: int = 3001


@dataclass
class ROSConfig:
    """ROS 2 connection settings."""

    node_name: str = "amazing_ros2_mcp"
    namespace: str = ""
    spin_timeout_sec: float = 0.1
    default_qos_depth: int = 10
    service_timeout_sec: float = 5.0
    # TF settings
    map_frame: str = "map"
    base_link_frame: str = "base_link"
    tf_timeout_sec: float = 0.5


@dataclass
class NavigationConfig:
    """Nav2 navigation settings (used when nav2 plugin loaded)."""

    max_waypoints: int = 100
    default_backup_speed: float = 0.2
    min_backup_distance: float = 0.01
    max_backup_distance: float = 10.0
    min_backup_speed: float = 0.01
    max_backup_speed: float = 1.0
    feedback_update_interval: int = 5


@dataclass
class LoggingConfig:
    """Logging settings."""

    level: int = logging.INFO
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class SafetyConfig:
    """Safety guardrails for robot commands."""

    # cmd_vel velocity caps
    max_linear_x: float = 1.0
    max_linear_y: float = 0.5
    max_angular_z: float = 1.5
    # Topics where publishing is blocked entirely
    blocked_topics: tuple = ()
    # When True, publish_message logs the command but does not actually publish
    dry_run: bool = False


@dataclass
class Config:
    """Root configuration combining all sections."""

    server: ServerConfig = field(default_factory=ServerConfig)
    ros: ROSConfig = field(default_factory=ROSConfig)
    navigation: NavigationConfig = field(default_factory=NavigationConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)

    def __post_init__(self):
        load_dotenv()
        self._load_env()
        self._validate()

    def _load_env(self):
        """Override config from environment variables."""
        if t := os.getenv("TRANSPORT_MODE"):
            if t in ("stdio", "http", "streamable-http"):
                self.server.transport = t
        if h := os.getenv("HTTP_HOST"):
            self.server.host = h
        if p := os.getenv("HTTP_PORT"):
            try:
                self.server.port = int(p)
            except ValueError:
                pass
        if lvl := os.getenv("LOG_LEVEL"):
            try:
                self.logging.level = getattr(logging, lvl.upper())
            except AttributeError:
                pass
        if ns := os.getenv("ROS_NAMESPACE"):
            self.ros.namespace = ns

    def _validate(self):
        """Validate config values."""
        nav = self.navigation
        if nav.min_backup_distance >= nav.max_backup_distance:
            raise ValueError("min_backup_distance must be < max_backup_distance")
        if nav.min_backup_speed >= nav.max_backup_speed:
            raise ValueError("min_backup_speed must be < max_backup_speed")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize config to dict."""
        return {
            "server": self.server.__dict__,
            "ros": self.ros.__dict__,
            "navigation": self.navigation.__dict__,
            "logging": {"level": self.logging.level, "format": self.logging.format},
        }


# Global singleton
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global config."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config) -> None:
    """Override global config."""
    global _config
    _config = config
