"""
Configuration and paths for gemini-cli-py.

Mirrors the role of `packages/core/src/config/` and `packages/core/src/utils/paths.ts`
in the original TypeScript gemini-cli, but adapted to Python idioms.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #


def home_dir() -> Path:
    """Return the user's home directory."""
    return Path.home()


def app_data_dir() -> Path:
    """Return the per-user app data directory (created lazily)."""
    env = os.environ.get("GEMINI_PY_HOME")
    if env:
        p = Path(env).expanduser()
    else:
        p = home_dir() / ".gemini-py"
    p.mkdir(parents=True, exist_ok=True)
    return p


def sessions_dir() -> Path:
    """Directory where conversation sessions are persisted as JSON."""
    env = os.environ.get("GEMINI_SESSIONS_DIR")
    if env:
        p = Path(env).expanduser()
    else:
        p = app_data_dir() / "sessions"
    p.mkdir(parents=True, exist_ok=True)
    return p


def settings_file() -> Path:
    """Path to the user settings JSON file."""
    return app_data_dir() / "settings.json"


def workspace_root() -> Path:
    """Root directory the agent operates in (current working dir by default)."""
    env = os.environ.get("GEMINI_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()
    return Path.cwd()


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #

# A curated registry of common Gemini models. The dropdown in the UI is
# populated from this list, but the model field is free-form — users can type
# any model name their API key has access to. This mirrors gemini-cli's
# `config/defaultModelConfigs.ts` + `config/models.ts`.

DEFAULT_MODELS: list[dict[str, str]] = [
    {
        "id": "gemini-2.5-flash",
        "label": "Gemini 2.5 Flash (fast, default)",
        "description": "Best for everyday tasks, fast responses, low cost.",
    },
    {
        "id": "gemini-2.5-pro",
        "label": "Gemini 2.5 Pro (reasoning)",
        "description": "Best for complex reasoning, long context, code generation.",
    },
    {
        "id": "gemini-2.5-flash-lite",
        "label": "Gemini 2.5 Flash-Lite",
        "description": "Lightest, cheapest, for high-volume low-latency tasks.",
    },
    {
        "id": "gemini-2.0-flash",
        "label": "Gemini 2.0 Flash",
        "description": "Previous-gen Flash, good fallback.",
    },
    {
        "id": "gemini-2.0-flash-exp",
        "label": "Gemini 2.0 Flash (experimental)",
        "description": "Experimental branch, may be unstable.",
    },
]

DEFAULT_MODEL_ID = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def model_id_to_label(model_id: str) -> str:
    for m in DEFAULT_MODELS:
        if m["id"] == model_id:
            return m["label"]
    return model_id


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


@dataclass
class Settings:
    """User-tunable settings, persisted to `settings.json`."""

    api_key: str = ""
    model: str = DEFAULT_MODEL_ID
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 40
    max_output_tokens: int = 65536
    system_prompt: str = ""
    approval_mode: str = "default"  # default | yolo | plan
    enable_streaming: bool = True
    enable_google_search: bool = True
    enable_shell: bool = True
    enable_web_fetch: bool = True
    enable_file_tools: bool = True
    enable_mcp: bool = False
    mcp_servers: list[dict[str, str]] = field(default_factory=list)

    # ---- persistence ---- #

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        path = settings_file()
        if path.exists():
            try:
                import json

                raw = json.loads(path.read_text(encoding="utf-8"))
                for k, v in raw.items():
                    if hasattr(s, k):
                        setattr(s, k, v)
            except Exception:
                # Corrupt settings file → start fresh
                pass
        # Environment variable takes precedence for the API key
        env_key = os.environ.get("GEMINI_API_KEY", "")
        if env_key:
            s.api_key = env_key
        return s

    def save(self) -> None:
        import json

        path = settings_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Never persist the API key if it came from the env var
        to_persist = {
            k: v
            for k, v in self.__dict__.items()
            if k != "api_key" or not os.environ.get("GEMINI_API_KEY")
        }
        path.write_text(
            json.dumps(to_persist, indent=2, default=str),
            encoding="utf-8",
        )

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# --------------------------------------------------------------------------- #
# Default system prompt
# --------------------------------------------------------------------------- #

DEFAULT_SYSTEM_PROMPT = """You are Gemini, an AI coding assistant embedded in a \
developer's terminal via a Gradio web UI. You are thoughtful, precise, and \
pragmatic.

You have access to a set of tools that let you read and edit files, list \
directories, run shell commands, fetch web pages, and search the web. Use them \
liberally to ground your answers in the user's actual codebase and the live web.

When the user asks you to do something:

1. If the task is about a codebase, **read the relevant files first** with the \
`read_file` or `read_many_files` tool, or `list_directory` to explore. Do not \
guess at file contents.
2. If the task requires running something (tests, scripts, git commands), use \
the `run_shell` tool. Capture stdout/stderr and report the result.
3. If you need real-time information, use `google_search` (grounded) or \
`web_fetch` (raw HTML → text).
4. When editing files, prefer the `edit_file` tool over `write_file` when the \
file already exists — it produces cleaner diffs.
5. After every tool call, briefly tell the user what you did and what you found, \
then continue with the next step or finish.

Be concise in your prose. Show code blocks with proper language tags. If you \
are uncertain, say so. If a tool fails, report the error and try an \
alternative approach.

You are running on the user's machine with their permissions. Be careful with \
destructive operations (rm, git push --force, etc.) — explain what you're \
about to do and let the user confirm if it seems risky.
"""
