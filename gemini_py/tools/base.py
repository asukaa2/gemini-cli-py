"""
Tool base class + registry.

Mirrors `packages/core/src/tools/tools.ts` and
`packages/core/src/tools/tool-registry.ts` in the original TS gemini-cli, but
in Pythonic form: a `Tool` ABC + a `ToolRegistry` that also exposes tools as
the `FunctionDeclaration` schema the Gemini SDK expects.
"""

from __future__ import annotations

import abc
import json
import shlex
from dataclasses import dataclass, field
from typing import Any, Optional

# --------------------------------------------------------------------------- #
# Tool result
# --------------------------------------------------------------------------- #


@dataclass
class ToolResult:
    """Standard tool return value. Serialized to a string for the LLM."""

    output: str = ""
    error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_llm_string(self) -> str:
        """How this result is presented back to the model."""
        prefix = "ERROR: " if self.error else ""
        return prefix + self.output


# --------------------------------------------------------------------------- #
# Tool base
# --------------------------------------------------------------------------- #


class Tool(abc.ABC):
    """Base class for all built-in tools."""

    name: str = ""
    description: str = ""
    # JSON-schema dict describing the tool's parameters, compatible with the
    # Gemini SDK's `FunctionDeclaration.parameters` field.
    parameters: dict[str, Any] = {}
    # If True, the user must approve each call before execution.
    requires_confirmation: bool = False

    @abc.abstractmethod
    def run(self, **kwargs) -> ToolResult:
        """Execute the tool with validated parameters. Subclasses must impl."""
        raise NotImplementedError

    # ---- helpers ---- #

    def declaration(self) -> dict[str, Any]:
        """Return the `FunctionDeclaration` dict consumed by the Gemini SDK."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters or {"type": "object", "properties": {}},
        }

    def safe_run(self, args: dict[str, Any]) -> ToolResult:
        """Validate args against `parameters` (loosely) then run the tool."""
        try:
            cleaned = _coerce_args(args, self.parameters)
            return self.run(**cleaned)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(output=f"{type(exc).__name__}: {exc}", error=True)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


class ToolRegistry:
    """Holds all enabled tools. Mirrors `tool-registry.ts`."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        if not tool.name:
            raise ValueError("Tool must have a `name` attribute")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def declarations(self) -> list[dict[str, Any]]:
        """All tool declarations, ready to pass to the Gemini SDK."""
        return [t.declaration() for t in self._tools.values()]

    def execute(self, name: str, args: dict[str, Any]) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                output=f"Unknown tool: {name!r}. Available: "
                + ", ".join(sorted(self._tools.keys())),
                error=True,
            )
        return tool.safe_run(args)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _coerce_args(args: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """
    Loosely coerce args to match the schema's expected types. The Gemini SDK
    sometimes returns numbers as floats when the schema wants ints, or omits
    optional fields entirely. We fill defaults from the schema.
    """
    if not schema or "properties" not in schema:
        return args
    out: dict[str, Any] = {}
    props = schema["properties"]
    for key, spec in props.items():
        if key in args and args[key] is not None:
            val = args[key]
            t = spec.get("type")
            if t == "integer" and isinstance(val, (float,)):
                val = int(val)
            elif t == "number" and isinstance(val, (int,)):
                val = float(val)
            elif t == "array" and isinstance(val, str):
                # Gemini occasionally returns arrays as JSON strings
                try:
                    val = json.loads(val)
                except Exception:
                    val = [val]
            elif t == "string" and not isinstance(val, str):
                val = str(val)
            out[key] = val
        elif "default" in spec:
            out[key] = spec["default"]
    return out


# --------------------------------------------------------------------------- #
# Shell argument quoting helper (used by run_shell and friends)
# --------------------------------------------------------------------------- #


def split_shell(command: str) -> list[str]:
    """Split a shell command string into argv using POSIX rules."""
    try:
        return shlex.split(command)
    except ValueError:
        # fall back to a naive split if shlex fails (e.g. unbalanced quotes)
        return command.split()
