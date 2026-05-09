from setuptools import find_packages, setup


setup(
    name="amazing-ros2-mcp",
    version="0.1.0",
    description="A native ROS 2 MCP server for AI-assisted robotics",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    author="proxi666",
    python_requires=">=3.10",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "fastmcp>=2.0.0",
        "anyio>=4.0.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "nav2": ["nav2_simple_commander"],
    },
    entry_points={
        "console_scripts": [
            "amazing-ros2-mcp=amazing_ros2_mcp.__main__:main",
        ],
    },
)
