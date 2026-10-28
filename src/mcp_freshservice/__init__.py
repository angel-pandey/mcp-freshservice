"""MCP server for the Freshservice ITSM API v2."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mcp-freshservice")
except PackageNotFoundError:  # running from a source checkout
    __version__ = "0.0.0"

__all__ = ["__version__", "main"]


def main() -> None:
    from .server import main as _main

    _main()
