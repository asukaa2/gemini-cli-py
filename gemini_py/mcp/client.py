"""
MCP (Model Context Protocol) client wrapper.

Mirrors a small subset of `packages/core/src/tools/mcp-client.ts` in the
original TS gemini-cli. We support stdio MCP servers via the official
`mcp` Python SDK; if `mcp` isn't installed, MCP support is silently
disabled.

Each MCP server is launched as a subprocess, its tools are discovered, and
those tools are exposed to the agent under their original names (prefixed
with the server name to avoid collisions).
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
from dataclasses import dataclass
from typing import Any, Optional

from ..config import Settings
from ..tools.base import Tool, ToolRegistry, ToolResult


# --------------------------------------------------------------------------- #
# MCP tool wrapper
# --------------------------------------------------------------------------- #


@dataclass
class MCPServerConfig:
    name: str
    command: str  # full command line, e.g. "npx -y @modelcontextprotocol/server-filesystem /tmp"
    env: dict[str, str] | None = None


class MCPToolWrapper(Tool):
    """Wraps a single tool exposed by an MCP server."""

    def __init__(self, server_name: str, tool_name: str, description: str, schema: dict, session_ref):
        self.name = f"mcp_{server_name}_{tool_name}"
        self.description = f"[MCP/{server_name}/{tool_name}] {description}"
        self.parameters = schema or {"type": "object", "properties": {}}
        self.requires_confirmation = True
        self._server_name = server_name
        self._tool_name = tool_name
        self._session_ref = session_ref  # weakref-like dict holding the session

    def run(self, **kwargs) -> ToolResult:
        sess = self._session_ref.get("session")
        if sess is None:
            return ToolResult(output="MCP session is not connected.", error=True)
        try:
            result = asyncio.run(sess.call_tool(self._tool_name, kwargs))
        except Exception as exc:
            return ToolResult(output=f"MCP call failed: {exc}", error=True)
        # `result` is a CallToolResult — extract text content
        text_parts: list[str] = []
        for c in getattr(result, "content", []) or []:
            t = getattr(c, "text", None)
            if t:
                text_parts.append(t)
        return ToolResult(output="\n".join(text_parts) or "(empty)")


# --------------------------------------------------------------------------- #
# Manager
# --------------------------------------------------------------------------- #


class MCPManager:
    """Manages a set of MCP server connections."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._sessions: dict[str, Any] = {}
        self._configs: dict[str, MCPServerConfig] = {}
        self._enabled = False
        self._available = _check_mcp_available()

    @property
    def available(self) -> bool:
        return self._available

    def parse_servers(self) -> list[MCPServerConfig]:
        """Parse MCP server configs from settings + env var."""
        configs: list[MCPServerConfig] = []
        # from settings
        for srv in self.settings.mcp_servers:
            configs.append(
                MCPServerConfig(
                    name=srv.get("name", "mcp"),
                    command=srv.get("command", ""),
                    env=srv.get("env"),
                )
            )
        # from GEMINI_MCP_SERVERS env var (newline- or semicolon-separated)
        env_raw = os.environ.get("GEMINI_MCP_SERVERS", "")
        for line in env_raw.replace(";", "\n").splitlines():
            line = line.strip()
            if not line:
                continue
            tokens = shlex.split(line)
            if not tokens:
                continue
            cmd = " ".join(shlex.quote(t) for t in tokens)
            configs.append(MCPServerConfig(name=tokens[0].split("/")[-1], command=cmd))
        return configs

    def connect_all(self, registry: ToolRegistry) -> list[str]:
        """
        Connect to all configured MCP servers and register their tools.
        Returns a list of human-readable status strings for the UI.
        """
        if not self._available:
            return ["MCP support disabled (install `mcp` package to enable)."]
        statuses: list[str] = []
        for cfg in self.parse_servers():
            try:
                status, tools = self._connect_one(cfg)
                statuses.append(status)
                for tool in tools:
                    registry.register(tool)
            except Exception as exc:
                statuses.append(f"[{cfg.name}] connection failed: {exc}")
        self._enabled = True
        return statuses

    def _connect_one(self, cfg: MCPServerConfig) -> tuple[str, list[Tool]]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        args = shlex.split(cfg.command)
        env = {**os.environ, **(cfg.env or {})}
        params = StdioServerParameters(command=args[0], args=args[1:], env=env)

        async def _setup():
            read, write = await stdio_client().__aenter__()
            session = ClientSession(read, write)
            await session.__aenter__()
            await session.initialize()
            tools_resp = await session.list_tools()
            return session, tools_resp.tools

        session, mcp_tools = asyncio.run(_setup())
        self._sessions[cfg.name] = session
        self._configs[cfg.name] = cfg

        wrapped: list[Tool] = []
        for t in mcp_tools:
            schema = _mcp_schema_to_json_schema(t.inputSchema)
            wrapper = MCPToolWrapper(
                server_name=cfg.name,
                tool_name=t.name,
                description=t.description or "",
                schema=schema,
                session_ref={"session": session},
            )
            wrapped.append(wrapper)
        status = f"[{cfg.name}] connected, {len(wrapped)} tool(s): " + ", ".join(
            t.name for t in wrapped
        )
        return status, wrapped

    def disconnect_all(self) -> None:
        for name, sess in list(self._sessions.items()):
            try:
                asyncio.run(sess.__aexit__(None, None, None))
            except Exception:
                pass
        self._sessions.clear()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _check_mcp_available() -> bool:
    try:
        import mcp  # noqa: F401

        return True
    except ImportError:
        return False


def _mcp_schema_to_json_schema(schema: Any) -> dict[str, Any]:
    """Convert an MCP tool's inputSchema to a plain JSON-schema dict."""
    if schema is None:
        return {"type": "object", "properties": {}}
    if isinstance(schema, dict):
        return schema
    if hasattr(schema, "to_dict"):
        try:
            return schema.to_dict()
        except Exception:
            pass
    try:
        return json.loads(str(schema))
    except Exception:
        return {"type": "object", "properties": {}}
