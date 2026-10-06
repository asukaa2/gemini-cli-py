"""Tool package — exports the registry factory and all built-in tools."""

from .base import Tool, ToolRegistry, ToolResult
from .builtin import (
    AskUserTool,
    EditFileTool,
    GlobTool,
    GoogleSearchTool,
    ListDirectoryTool,
    ReadFileTool,
    ReadManyFilesTool,
    RunShellTool,
    WebFetchTool,
    WriteFileTool,
)


def build_default_registry(client=None, settings=None) -> ToolRegistry:
    """
    Construct a ToolRegistry with the built-in tools enabled according to the
    user's settings. `client` is the GeminiClient (used by google_search).
    """
    reg = ToolRegistry()

    # File tools
    if settings is None or settings.enable_file_tools:
        reg.register(ReadFileTool())
        reg.register(WriteFileTool())
        reg.register(EditFileTool())
        reg.register(ListDirectoryTool())
        reg.register(ReadManyFilesTool())
        reg.register(GlobTool())

    # Shell
    if settings is None or settings.enable_shell:
        reg.register(RunShellTool())

    # Web
    if settings is None or settings.enable_web_fetch:
        reg.register(WebFetchTool())

    # Google Search grounding
    if settings is None or settings.enable_google_search:
        reg.register(GoogleSearchTool(client=client))

    # ask_user is always available
    reg.register(AskUserTool())

    return reg


__all__ = [
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "build_default_registry",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "ListDirectoryTool",
    "ReadManyFilesTool",
    "RunShellTool",
    "WebFetchTool",
    "GoogleSearchTool",
    "GlobTool",
    "AskUserTool",
]
