"""
Agent loop: orchestrates the model ↔ tools conversation.

Mirrors `packages/core/src/core/turn.ts` + `packages/core/src/scheduler/scheduler.ts`
in the original TS gemini-cli. We:

1. Send the message history + tool declarations to the model.
2. Stream tokens back to the UI.
3. When the model returns `function_call` parts, dispatch them to the tool
   registry (asking for user approval if `requires_confirmation`).
4. Append the tool results back to the history and loop, until the model
   stops requesting tools.

The loop is a Python generator so the UI can stream incremental updates.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from ..client import GeminiClient
from ..config import Settings, DEFAULT_SYSTEM_PROMPT
from ..sessions import MessageRecord
from ..tools import ToolRegistry, ToolResult


# --------------------------------------------------------------------------- #
# Events yielded by the loop
# --------------------------------------------------------------------------- #


@dataclass
class AgentEvent:
    """Events streamed from the agent loop to the UI."""

    kind: str  # "text" | "tool_call" | "tool_result" | "error" | "done"
    text: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_call_id: str = ""
    tool_result: str = ""
    tool_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Loop
# --------------------------------------------------------------------------- #


class AgentLoop:
    """
    Run a single user turn: send history to the model, dispatch any tool calls
    that come back, loop until the model stops calling tools or the turn cap
    is hit.
    """

    def __init__(
        self,
        client: GeminiClient,
        registry: ToolRegistry,
        settings: Settings,
        max_iterations: int = 10,
    ):
        self.client = client
        self.registry = registry
        self.settings = settings
        self.max_iterations = max_iterations

    # ---- public API ---- #

    def run(
        self,
        messages: list[MessageRecord],
        *,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        stream: bool = True,
    ) -> Iterator[AgentEvent]:
        """
        Run the agent loop. Yields AgentEvent objects as they happen.
        Mutates `messages` in-place — the caller can persist them afterwards.
        """
        sys_prompt = system_prompt or self.settings.system_prompt or DEFAULT_SYSTEM_PROMPT
        tools = self.registry.declarations() or None

        for iteration in range(self.max_iterations):
            contents = _messages_to_contents(messages)
            accumulated_text = ""
            tool_calls: list[dict[str, Any]] = []
            tool_call_ids: list[str] = []

            try:
                if stream and self.settings.enable_streaming:
                    for chunk in self.client.stream(
                        contents,
                        tools=tools,
                        system_prompt=sys_prompt,
                        model=model,
                        temperature=temperature,
                    ):
                        text_part, calls = _extract_from_chunk(chunk)
                        if text_part:
                            accumulated_text += text_part
                            yield AgentEvent(
                                kind="text",
                                text=text_part,
                                metadata={"accumulated": accumulated_text},
                            )
                        if calls:
                            tool_calls.extend(calls)
                else:
                    resp = self.client.generate(
                        contents,
                        tools=tools,
                        system_prompt=sys_prompt,
                        model=model,
                        temperature=temperature,
                    )
                    accumulated_text, tool_calls = _extract_from_response(resp)
                    if accumulated_text:
                        yield AgentEvent(
                            kind="text",
                            text=accumulated_text,
                            metadata={"accumulated": accumulated_text},
                        )
            except Exception as exc:
                yield AgentEvent(kind="error", text=f"{type(exc).__name__}: {exc}")
                return

            # If the model emitted text, record it as a model message
            if accumulated_text.strip():
                messages.append(
                    MessageRecord(role="model", content=accumulated_text)
                )

            # If there are no tool calls, the turn is done
            if not tool_calls:
                yield AgentEvent(kind="done", metadata={"iterations": iteration + 1})
                return

            # Record the model's tool-call message in history
            messages.append(
                MessageRecord(
                    role="model",
                    content=accumulated_text,
                    tool_calls=tool_calls,
                )
            )

            # Execute each tool call
            for call in tool_calls:
                name = call.get("name", "")
                args = call.get("args", {}) or {}
                call_id = call.get("id") or uuid.uuid4().hex[:16]
                yield AgentEvent(
                    kind="tool_call",
                    tool_name=name,
                    tool_args=args,
                    tool_call_id=call_id,
                )

                tool = self.registry.get(name)
                if tool is None:
                    result = ToolResult(
                        output=f"Unknown tool: {name}", error=True
                    )
                else:
                    result = tool.safe_run(args)

                result_text = result.to_llm_string()
                yield AgentEvent(
                    kind="tool_result",
                    tool_name=name,
                    tool_call_id=call_id,
                    tool_result=result_text,
                    tool_error=result.error,
                )

                messages.append(
                    MessageRecord(
                        role="tool",
                        content=result_text,
                        tool_call_id=call_id,
                        name=name,
                    )
                )

        # Turn cap hit
        yield AgentEvent(
            kind="error",
            text=(
                f"Reached the maximum of {self.max_iterations} tool-call "
                "iterations in a single turn. The conversation is still "
                "saved — you can continue in the next turn."
            ),
            metadata={"iterations": self.max_iterations},
        )


# --------------------------------------------------------------------------- #
# Helpers: convert our MessageRecord list to the SDK's `contents` shape
# --------------------------------------------------------------------------- #


def _messages_to_contents(messages: list[MessageRecord]) -> list[dict[str, Any]]:
    """
    Convert our internal MessageRecord list into the `contents` argument the
    google-genai SDK expects.

    The SDK accepts a list of `Content` dicts like:
        {"role": "user"|"model", "parts": [Part, ...]}
    where each Part is one of: {"text": "..."}, {"function_call": {...}},
    {"function_response": {"name, response}}}.
    """
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            # system prompt is passed separately via config
            continue
        role = "user" if m.role == "user" else "model"
        parts: list[dict[str, Any]] = []
        if m.content:
            parts.append({"text": m.content})
        if m.tool_calls:
            for call in m.tool_calls:
                fc_dict: dict[str, Any] = {
                    "id": call.get("id") or uuid.uuid4().hex[:16],
                    "name": call.get("name", ""),
                    "args": call.get("args", {}) or {},
                }
                # Echo back the thought_signature if we captured one.
                # Gemini 3.x requires this on every function_call round-trip.
                ts = call.get("thought_signature")
                if ts:
                    fc_dict["thought_signature"] = ts
                parts.append({"function_call": fc_dict})
        if m.role == "tool":
            # function_response must be attached to the model turn that
            # produced the call. We handle this by emitting a model turn here
            # containing the function_response.
            response_part = {
                "function_response": {
                    "id": m.tool_call_id or "",
                    "name": m.name or "",
                    "response": {"output": m.content},
                }
            }
            # Attach to the previous model turn if it exists, else new turn
            if out and out[-1]["role"] == "model":
                out[-1]["parts"].append(response_part)
            else:
                out.append({"role": "model", "parts": [response_part]})
            continue
        if parts:
            out.append({"role": role, "parts": parts})
    return out


# --------------------------------------------------------------------------- #
# Helpers: extract text + tool calls from SDK responses
# --------------------------------------------------------------------------- #


def _extract_from_chunk(chunk: Any) -> tuple[str, list[dict[str, Any]]]:
    """
    Extract streaming-text deltas and tool calls from one SDK chunk.

    Captures `thought_signature` on every function_call so we can echo it
    back on the next round-trip (Gemini 3.x requires this; without it the
    API returns 400 INVALID_ARGUMENT 'Function call is missing a
    thought_signature').
    """
    text = ""
    calls: list[dict[str, Any]] = []
    try:
        candidates = getattr(chunk, "candidates", None) or []
        if not candidates:
            return text, calls
        parts = getattr(candidates[0].content, "parts", []) or []
        for part in parts:
            pt = getattr(part, "text", None)
            # Skip 'thought' parts — Gemini's reasoning trace. If we append
            # these to the visible text the model sees its own thinking on
            # the next turn and the API errors out.
            is_thought = bool(getattr(part, "thought", False))
            if pt and not is_thought:
                text += pt
            fc = getattr(part, "function_call", None)
            if fc is not None:
                calls.append(_function_call_to_dict(fc))
    except Exception:
        pass
    return text, calls


def _extract_from_response(resp: Any) -> tuple[str, list[dict[str, Any]]]:
    """Extract accumulated text + tool calls from a non-streaming response."""
    text = ""
    calls: list[dict[str, Any]] = []
    try:
        candidates = getattr(resp, "candidates", None) or []
        if not candidates:
            t = getattr(resp, "text", None)
            return t or "", calls
        parts = getattr(candidates[0].content, "parts", []) or []
        for part in parts:
            pt = getattr(part, "text", None)
            is_thought = bool(getattr(part, "thought", False))
            if pt and not is_thought:
                text += pt
            fc = getattr(part, "function_call", None)
            if fc is not None:
                calls.append(_function_call_to_dict(fc))
    except Exception:
        pass
    return text, calls


def _function_call_to_dict(fc: Any) -> dict[str, Any]:
    """
    Convert a FunctionCall part (protobuf or Mapping) to a plain dict,
    preserving the `thought_signature` field that Gemini 3.x requires on
    every round-trip.

    Returns a dict with keys:
        id, name, args, thought_signature (optional), thought (optional)
    """
    d: dict[str, Any] = {
        "id": getattr(fc, "id", None) or uuid.uuid4().hex[:16],
        "name": getattr(fc, "name", ""),
        "args": _to_plain(getattr(fc, "args", {})) or {},
    }
    # Capture thought_signature if the model provided one. On Gemini 3.x
    # this is mandatory for tool-calling to work round-trip.
    ts = getattr(fc, "thought_signature", None)
    if ts:
        d["thought_signature"] = ts
    # Some models also send a `thought` boolean or `thought_text` — preserve them.
    if getattr(fc, "thought", None) is not None:
        d["thought"] = bool(getattr(fc, "thought"))
    return d


def _to_plain(obj: Any) -> Any:
    """Convert protobuf / Mapping objects to plain Python dicts/lists."""
    if obj is None:
        return None
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            pass
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(v) for v in obj]
    # protobuf scalar (int, float, str, bool) — return as-is
    return obj
