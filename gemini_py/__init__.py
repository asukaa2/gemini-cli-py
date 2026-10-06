"""
gemini_py — Python + Gradio port of google-gemini/gemini-cli.

Public API:
    Settings, GeminiClient, AgentLoop, AgentEvent, ToolRegistry,
    build_default_registry, SessionStore, Session, MessageRecord, MCPManager
"""

from .agents import AgentEvent, AgentLoop
from .client import AuthError, GeminiClient
from .config import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODELS,
    DEFAULT_SYSTEM_PROMPT,
    Settings,
    app_data_dir,
    sessions_dir,
    workspace_root,
)
from .mcp import MCPManager
from .sessions import MessageRecord, Session, SessionStore
from .tools import (
    Tool,
    ToolRegistry,
    ToolResult,
    build_default_registry,
)

__version__ = "0.1.0"

__all__ = [
    "AgentEvent",
    "AgentLoop",
    "AuthError",
    "DEFAULT_MODEL_ID",
    "DEFAULT_MODELS",
    "DEFAULT_SYSTEM_PROMPT",
    "GeminiClient",
    "MCPManager",
    "MessageRecord",
    "Session",
    "SessionStore",
    "Settings",
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "app_data_dir",
    "build_default_registry",
    "sessions_dir",
    "workspace_root",
]
