"""
Gradio UI for gemini-cli-py.

Two-pane Blocks layout:
  • Left  — Chat pane (model picker, system prompt, streaming, tool-call cards,
            file upload, sessions list).
  • Right — Workspace pane (file tree of the workspace root, file viewer,
            diff viewer for the last edit_file / write_file call).

Mirrors the visual role of `packages/cli/src/ui/` in the original TS gemini-cli,
adapted to the web via Gradio.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import gradio as gr

from ..agents import AgentEvent, AgentLoop
from ..client import AuthError, GeminiClient
from ..config import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODELS,
    DEFAULT_SYSTEM_PROMPT,
    Settings,
    workspace_root,
)
from ..mcp import MCPManager
from ..sessions import MessageRecord, Session, SessionStore
from ..tools import build_default_registry


# --------------------------------------------------------------------------- #
# App state (one instance per Gradio app instance)
# --------------------------------------------------------------------------- #


class AppState:
    """Mutable state shared across Gradio callbacks for a single app instance."""

    def __init__(self) -> None:
        self.settings = Settings.load()
        self.client = GeminiClient(self.settings)
        self.sessions = SessionStore()
        self.mcp = MCPManager(self.settings)
        self.registry = build_default_registry(client=self.client, settings=self.settings)
        self.current_session: Optional[Session] = None

    # ---- session helpers ---- #

    def ensure_session(self) -> Session:
        if self.current_session is None:
            self.current_session = self.sessions.create()
        return self.current_session

    def switch_session(self, sid: str) -> Session:
        s = self.sessions.load(sid)
        if s is None:
            s = self.sessions.create()
        self.current_session = s
        return s

    # ---- rebuilders ---- #

    def rebuild_client(self) -> None:
        self.client = GeminiClient(self.settings)
        self.registry = build_default_registry(
            client=self.client, settings=self.settings
        )

    def connect_mcp(self) -> list[str]:
        if not self.settings.enable_mcp:
            return ["MCP support is toggled off in settings."]
        return self.mcp.connect_all(self.registry)


# --------------------------------------------------------------------------- #
# Main build
# --------------------------------------------------------------------------- #


def build_app() -> gr.Blocks:
    state = AppState()

    # CSS + theme are passed to launch() in Gradio 6.x (see `_CUSTOM_CSS`
    # at the bottom of this file). We deliberately do NOT pass a theme —
    # Gradio's built-in default is used.
    with gr.Blocks(title="Gemini CLI (Python + Gradio)") as app:
        gr.Markdown(
            "# 🤖 Gemini CLI — Python + Gradio Edition\n"
            "A web UI port of Google's [gemini-cli](https://github.com/google-gemini/gemini-cli), "
            "rewritten in Python with [Gradio](https://gradio.app). "
            "Chat with Gemini, run tools (file ops, shell, web fetch, Google Search), "
            "and inspect the workspace side-by-side."
        )

        # --------------------------------------------------------------- #
        # Top status bar
        # --------------------------------------------------------------- #
        with gr.Row():
            api_status = gr.Markdown(
                _render_api_status(state.settings), elem_id="api-status"
            )
            mcp_status = gr.Markdown(
                _render_mcp_status(state.mcp, state.settings), elem_id="mcp-status"
            )
            ws_status = gr.Markdown(
                f"📂 **Workspace:** `{workspace_root()}`", elem_id="ws-status"
            )

        # --------------------------------------------------------------- #
        # Two-pane layout
        # --------------------------------------------------------------- #
        with gr.Row(equal_height=False):
            # ---------- LEFT: chat pane ---------- #
            with gr.Column(scale=3, elem_id="chat-pane"):
                # --- session row ---
                with gr.Row():
                    session_dd = gr.Dropdown(
                        choices=_session_choices(state.sessions),
                        value=None,
                        label="Conversation",
                        scale=4,
                        interactive=True,
                    )
                    new_btn = gr.Button("➕ New", scale=1)
                    del_btn = gr.Button("🗑 Delete", scale=1)

                # --- chat window ---
                chat = gr.Chatbot(
                    value=[],
                    label="Chat",
                    height=440,
                    buttons=["copy"],
                    render_markdown=True,
                    avatar_images=(
                        None,
                        "https://www.gstatic.com/lamda/images/favicon_bf162465427c8404.svg",
                    ),
                )

                # --- input row ---
                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="Ask Gemini anything… (Shift+Enter for newline)",
                        lines=3,
                        scale=5,
                        show_label=False,
                    )
                    send_btn = gr.Button("📤 Send", scale=1, variant="primary")
                    stop_btn = gr.Button("⏹ Stop", scale=1, variant="stop")

                # --- file upload ---
                with gr.Accordion("📎 Attach files (images / PDFs)", open=False):
                    upload = gr.File(
                        label="Drop files here",
                        file_count="multiple",
                        file_types=["image", ".pdf", ".txt", ".md", ".json", ".csv"],
                    )

            # ---------- RIGHT: workspace pane ---------- #
            with gr.Column(scale=2, elem_id="workspace-pane"):
                gr.Markdown("### 📂 Workspace")
                file_tree = gr.Code(
                    value=_render_file_tree(workspace_root()),
                    label="File tree",
                    language=None,
                    lines=25,
                )
                with gr.Row():
                    refresh_btn = gr.Button("🔄 Refresh", size="sm")
                    path_input = gr.Textbox(
                        label="Path to view", value=".", scale=2, interactive=True
                    )
                    view_btn = gr.Button("👁 View", size="sm")
                file_view = gr.Code(
                    label="File contents",
                    language=None,
                    lines=25,
                    interactive=False,
                )

        # --------------------------------------------------------------- #
        # Settings accordion
        # --------------------------------------------------------------- #
        with gr.Accordion("⚙️ Settings", open=False):
            with gr.Row():
                api_key = gr.Textbox(
                    label="GEMINI_API_KEY",
                    value=state.settings.api_key,
                    type="password",
                    placeholder="Paste your API key from https://aistudio.google.com/apikey",
                    scale=3,
                )
                model_dd = gr.Dropdown(
                    label="Model",
                    choices=[m["id"] for m in DEFAULT_MODELS] + state.client.list_models(),
                    value=state.settings.model,
                    allow_custom_value=True,
                    scale=2,
                )
                temperature = gr.Slider(
                    label="Temperature",
                    minimum=0.0,
                    maximum=2.0,
                    step=0.1,
                    value=state.settings.temperature,
                    scale=1,
                )
            with gr.Row():
                streaming = gr.Checkbox(
                    label="Stream tokens",
                    value=state.settings.enable_streaming,
                    scale=1,
                )
                google_search = gr.Checkbox(
                    label="Google Search grounding",
                    value=state.settings.enable_google_search,
                    scale=1,
                )
                shell_tool = gr.Checkbox(
                    label="Shell tool",
                    value=state.settings.enable_shell,
                    scale=1,
                )
                mcp_toggle = gr.Checkbox(
                    label="MCP client",
                    value=state.settings.enable_mcp,
                    scale=1,
                )
            system_prompt_ta = gr.TextArea(
                label="System prompt",
                value=state.settings.system_prompt or DEFAULT_SYSTEM_PROMPT,
                lines=8,
            )
            with gr.Row():
                save_btn = gr.Button("💾 Save settings", variant="primary")
                reload_models_btn = gr.Button("🔄 Reload models list")
                connect_mcp_btn = gr.Button("🔌 Connect MCP servers")

        # --------------------------------------------------------------- #
        # Wire up callbacks
        # --------------------------------------------------------------- #

        # ---- Send message ---- #
        async def on_send(message_text, history, uploads, model, temp, stream, gs, shell, mcp_on):
            # Apply runtime settings overrides
            state.settings.model = model or DEFAULT_MODEL_ID
            state.settings.temperature = float(temp)
            state.settings.enable_streaming = bool(stream)
            state.settings.enable_google_search = bool(gs)
            state.settings.enable_shell = bool(shell)
            state.settings.enable_mcp = bool(mcp_on)
            # Rebuild registry if toggles changed
            state.rebuild_client()
            if state.settings.enable_mcp:
                state.connect_mcp()

            session = state.ensure_session()
            session.model = state.settings.model

            # Build the user message (with attached files as inline data)
            parts_text = message_text.strip()
            if not parts_text and not uploads:
                yield history, ""
                return

            # Append the user turn to history + session
            history = history or []
            display_text = parts_text
            attached_summaries: list[str] = []
            inline_parts: list[dict[str, Any]] = []
            if uploads:
                for f in uploads:
                    try:
                        attached_summaries.append(f"📎 {os.path.basename(f.name)}")
                        inline_parts.extend(_file_to_inline_parts(f))
                    except Exception as exc:
                        attached_summaries.append(f"⚠️ {os.path.basename(f.name)}: {exc}")
            if attached_summaries:
                display_text += "\n\n" + " ".join(attached_summaries)
            history.append({"role": "user", "content": display_text})
            session.messages.append(
                MessageRecord(role="user", content=parts_text or "(file attachments)")
            )

            # Build the agent loop and stream events
            loop = AgentLoop(
                client=state.client,
                registry=state.registry,
                settings=state.settings,
            )
            system_prompt = state.settings.system_prompt or DEFAULT_SYSTEM_PROMPT

            # Stream the model's response
            accumulated = ""
            tool_event_count = 0
            # We yield a placeholder assistant message that we mutate as events arrive
            assistant_msg = {"role": "assistant", "content": ""}
            history.append(assistant_msg)
            yield history, ""

            try:
                for event in loop.run(
                    session.messages,
                    system_prompt=system_prompt,
                    model=state.settings.model,
                    temperature=state.settings.temperature,
                    stream=state.settings.enable_streaming,
                ):
                    if event.kind == "text":
                        accumulated = event.metadata.get("accumulated", accumulated + event.text)
                        assistant_msg["content"] = accumulated
                        yield history, ""
                    elif event.kind == "tool_call":
                        # Append a tool-call card to history
                        card_md = _render_tool_call_card(event)
                        history.append({"role": "assistant", "content": card_md})
                        tool_event_count += 1
                        yield history, ""
                    elif event.kind == "tool_result":
                        card_md = _render_tool_result_card(event)
                        history.append({"role": "assistant", "content": card_md})
                        # Refresh the file tree if the tool touched files
                        if event.tool_name in {"write_file", "edit_file", "list_directory", "run_shell"}:
                            pass  # the workspace refresh happens via separate callback
                        yield history, ""
                    elif event.kind == "error":
                        assistant_msg["content"] = (
                            (assistant_msg["content"] or "") + f"\n\n⚠️ {event.text}"
                        )
                        yield history, ""
                    elif event.kind == "done":
                        # final yield
                        pass
            except AuthError as exc:
                assistant_msg["content"] = (
                    f"⚠️ Authentication error: {exc}\n\nPlease paste your "
                    "GEMINI_API_KEY in the Settings panel below."
                )
                yield history, ""
            except Exception as exc:
                assistant_msg["content"] = (
                    (assistant_msg["content"] or "")
                    + f"\n\n⚠️ Error: {type(exc).__name__}: {exc}"
                )
                yield history, ""

            # Persist the session
            state.sessions.save(session)

        send_event_kwargs = dict(
            inputs=[
                msg, chat, upload, model_dd, temperature,
                streaming, google_search, shell_tool, mcp_toggle,
            ],
            outputs=[chat, msg],
        )

        # Use streaming-aware click / submit. Gradio 5 supports async generators.
        send_btn.click(on_send, **send_event_kwargs)
        msg.submit(on_send, **send_event_kwargs)

        # ---- New session ---- #
        def on_new():
            s = state.sessions.create()
            state.current_session = s
            return gr.update(value=s.id, choices=_session_choices(state.sessions)), []

        new_btn.click(on_new, outputs=[session_dd, chat])

        # ---- Delete session ---- #
        def on_delete(sid):
            if sid:
                state.sessions.delete(sid)
            state.current_session = None
            return gr.update(choices=_session_choices(state.sessions), value=None), []

        del_btn.click(on_delete, inputs=[session_dd], outputs=[session_dd, chat])

        # ---- Switch session ---- #
        def on_switch(sid):
            if not sid:
                return [], gr.update(value=None)
            s = state.switch_session(sid)
            history = _session_to_history(s)
            return history, gr.update(value=s.id)

        session_dd.change(on_switch, inputs=[session_dd], outputs=[chat, session_dd])

        # ---- Refresh file tree ---- #
        def on_refresh_tree():
            return _render_file_tree(workspace_root())

        refresh_btn.click(on_refresh_tree, outputs=[file_tree])

        # ---- View file ---- #
        def on_view(path):
            if not path:
                return "(no path)"
            p = (workspace_root() / path).resolve() if not os.path.isabs(path) else Path(path)
            try:
                rel = p.relative_to(workspace_root())
            except ValueError:
                rel = p
            if not p.exists():
                return f"not found: {rel}"
            if p.is_dir():
                return _render_file_tree(p, max_depth=3)
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                return f"read failed: {exc}"
            # cap to 5000 chars for display
            if len(text) > 5000:
                text = text[:5000] + f"\n\n… ({len(text) - 5000} more chars)"
            return text

        view_btn.click(on_view, inputs=[path_input], outputs=[file_view])
        path_input.submit(on_view, inputs=[path_input], outputs=[file_view])

        # ---- Save settings ---- #
        def on_save(key, model, temp, stream, gs, shell, mcp_on, sys_prompt):
            state.settings.api_key = key
            state.settings.model = model
            state.settings.temperature = float(temp)
            state.settings.enable_streaming = bool(stream)
            state.settings.enable_google_search = bool(gs)
            state.settings.enable_shell = bool(shell)
            state.settings.enable_mcp = bool(mcp_on)
            state.settings.system_prompt = sys_prompt
            state.settings.save()
            # rebuild the client + registry with new settings
            state.rebuild_client()
            if state.settings.enable_mcp:
                mcp_lines = state.connect_mcp()
            else:
                mcp_lines = ["MCP disabled."]
            return (
                _render_api_status(state.settings),
                _render_mcp_status(state.mcp, state.settings),
                gr.update(choices=[m["id"] for m in DEFAULT_MODELS] + state.client.list_models(), value=model),
            )

        save_btn.click(
            on_save,
            inputs=[
                api_key, model_dd, temperature, streaming,
                google_search, shell_tool, mcp_toggle, system_prompt_ta,
            ],
            outputs=[api_status, mcp_status, model_dd],
        )

        # ---- Reload models list ---- #
        def on_reload_models():
            ids = state.client.list_models()
            return gr.update(choices=[m["id"] for m in DEFAULT_MODELS] + ids)

        reload_models_btn.click(on_reload_models, outputs=[model_dd])

        # ---- Connect MCP ---- #
        def on_connect_mcp():
            lines = state.connect_mcp()
            return _render_mcp_status(state.mcp, state.settings, lines)

        connect_mcp_btn.click(on_connect_mcp, outputs=[mcp_status])

    return app


# --------------------------------------------------------------------------- #
# Helpers: rendering
# --------------------------------------------------------------------------- #


def _render_api_status(settings: Settings) -> str:
    if settings.api_key:
        masked = settings.api_key[:6] + "…" + settings.api_key[-4:]
        return f'<span class="status-pill status-ok">🔑 API key: {masked}</span>'
    return (
        '<span class="status-pill status-err">🔑 No API key — '
        "set GEMINI_API_KEY env var or paste in Settings</span>"
    )


def _render_mcp_status(mcp: MCPManager, settings: Settings, lines: list[str] | None = None) -> str:
    if not settings.enable_mcp:
        return '<span class="status-pill status-warn">🔌 MCP: off</span>'
    if not mcp.available:
        return '<span class="status-pill status-warn">🔌 MCP: package not installed</span>'
    if lines:
        body = "<br>".join(l for l in lines)
        return f'<span class="status-pill status-ok">🔌 MCP connected</span><br><small>{body}</small>'
    return '<span class="status-pill status-ok">🔌 MCP: ready</span>'


def _session_choices(store: SessionStore) -> list[str]:
    out: list[str] = []
    for s in store.list_sessions():
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(s.updated_at))
        label = f"{s.id} — {s.title[:40]} ({ts})"
        out.append(label)
    return out


def _session_to_history(session: Session) -> list[dict[str, str]]:
    """Convert a Session's MessageRecords into Gradio chatbot message dicts."""
    out: list[dict[str, str]] = []
    for m in session.messages:
        if m.role == "user":
            out.append({"role": "user", "content": m.content})
        elif m.role == "model":
            if m.tool_calls:
                for call in m.tool_calls:
                    ev = AgentEvent(
                        kind="tool_call",
                        tool_name=call.get("name", ""),
                        tool_args=call.get("args", {}) or {},
                        tool_call_id=call.get("id", ""),
                    )
                    out.append({"role": "assistant", "content": _render_tool_call_card(ev)})
            if m.content:
                out.append({"role": "assistant", "content": m.content})
        elif m.role == "tool":
            ev = AgentEvent(
                kind="tool_result",
                tool_name=m.name or "",
                tool_call_id=m.tool_call_id or "",
                tool_result=m.content,
                tool_error=False,
            )
            out.append({"role": "assistant", "content": _render_tool_result_card(ev)})
    return out


def _render_tool_call_card(event: AgentEvent) -> str:
    args_str = json.dumps(event.tool_args, indent=2, default=str)
    return (
        f'<div class="tool-card"><span class="tool-name">🔧 {event.tool_name}</span>'
        f'<pre>{_escape_html(args_str)}</pre></div>'
    )


def _render_tool_result_card(event: AgentEvent) -> str:
    cls = "tool-card error" if event.tool_error else "tool-card"
    result_str = event.tool_result
    if len(result_str) > 4000:
        result_str = result_str[:4000] + "\n… (truncated)"
    return (
        f'<div class="{cls}"><span class="tool-name">{"❌" if event.tool_error else "✅"} '
        f"{event.tool_name} (result)</span>"
        f'<pre>{_escape_html(result_str)}</pre></div>'
    )


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _render_file_tree(root: Path, max_depth: int = 2) -> str:
    lines: list[str] = []
    # Always exclude these noisy / huge dirs
    exclude = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".cache"}
    try:
        for path in sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if path.name in exclude or path.name.startswith("."):
                continue
            if path.is_dir():
                lines.append(f"📁 {path.name}/")
                if max_depth > 1:
                    for sub in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:8]:
                        if sub.name in exclude:
                            continue
                        is_dir = sub.is_dir()
                        lines.append(f"   {'📁' if is_dir else '📄'} {sub.name}{'/' if is_dir else ''}")
                    try:
                        extra = len(list(path.iterdir())) - 8
                        if extra > 0:
                            lines.append(f"   … (+{extra} more)")
                    except Exception:
                        pass
            else:
                lines.append(f"📄 {path.name}")
    except Exception as exc:
        lines.append(f"(error reading tree: {exc})")
    return "\n".join(lines) if lines else "(empty workspace)"


def _file_to_inline_parts(file_obj) -> list[dict[str, Any]]:
    """
    Convert a Gradio File object to inline_data parts the Gemini SDK accepts.
    Handles images (PNG/JPEG/WebP/GIF) and PDFs.
    """
    out: list[dict[str, Any]] = []
    path = Path(file_obj.name)
    mime = _guess_mime(path)
    data = path.read_bytes()
    if mime.startswith("image/") or mime == "application/pdf":
        b64 = base64.b64encode(data).decode("ascii")
        out.append({
            "inline_data": {
                "mime_type": mime,
                "data": b64,
            }
        })
    else:
        # text-based attachment → include as text
        try:
            text = data.decode("utf-8", errors="replace")
            out.append({"text": f"\n\nAttached file `{path.name}`:\n```\n{text[:8000]}\n```"})
        except Exception:
            pass
    return out


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".json": "application/json",
        ".csv": "text/csv",
    }.get(ext, "application/octet-stream")


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #


def launch(**kwargs) -> None:
    """
    Build the app and launch a Gradio server.

    Args:
        **kwargs: Passed through to ``gr.Blocks.launch()``. Pass ``share=True``
            to get a public ``*.gradio.live`` URL printed to stdout (Gradio's
            native share feature). We deliberately do not set a theme here
            so Gradio's built-in default styling is used.
    """
    app = build_app()
    app.queue(default_concurrency_limit=4)
    # Gradio 6.x moved theme + css from Blocks() to launch(). We only set
    # CSS (for the tool-card styling) — no theme override, so Gradio's
    # native default theme is used.
    kwargs.setdefault("css", _CUSTOM_CSS)
    app.launch(**kwargs)


# Module-level CSS string so launch() can pass it to Blocks.launch()
_CUSTOM_CSS = """
#chat-pane { min-height: 70vh; }
#workspace-pane { min-height: 70vh; background: #fafafa; }
.tool-card {
    border: 1px solid #e0e0e0; border-radius: 8px; padding: 8px 12px;
    margin: 6px 0; background: #f6f8fa; font-size: 13px;
}
.tool-card.error { border-color: #ff6b6b; background: #fff0f0; }
.tool-card .tool-name { font-weight: 600; color: #2563eb; }
.tool-card pre { background: #fff; padding: 6px; border-radius: 4px;
                overflow-x: auto; font-size: 12px; margin: 4px 0; }
.status-pill {
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 11px; font-weight: 600;
}
.status-ok { background: #dcfce7; color: #166534; }
.status-warn { background: #fef3c7; color: #92400e; }
.status-err { background: #fee2e2; color: #991b1b; }
"""
