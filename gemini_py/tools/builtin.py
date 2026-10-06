"""
Built-in tools: read_file, write_file, edit_file, list_directory,
read_many_files, run_shell, web_fetch, google_search, glob, ask_user.

Mirrors the tools under `packages/core/src/tools/` in the original TS gemini-cli.
Each tool subclasses `Tool` from `base.py`.
"""

from __future__ import annotations

import asyncio
import fnmatch
import os
import re
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Optional

from ..config import workspace_root
from .base import Tool, ToolResult


# --------------------------------------------------------------------------- #
# Path safety
# --------------------------------------------------------------------------- #


def _resolve(path: str) -> Path:
    """Resolve `path` against the workspace root, preventing escape."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = workspace_root() / p
    return p.resolve()


def _is_path_safe(p: Path) -> bool:
    """Return True if `p` is inside the workspace root."""
    try:
        p.relative_to(workspace_root())
        return True
    except ValueError:
        return False


def _truncate(text: str, max_chars: int = 200_000) -> str:
    """Truncate very large tool outputs so we don't blow the context window."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return (
        text[:half]
        + f"\n\n… [truncated {len(text) - max_chars:,} chars] …\n\n"
        + text[-half:]
    )


# --------------------------------------------------------------------------- #
# read_file
# --------------------------------------------------------------------------- #


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read the full contents of a UTF-8 text file relative to the workspace "
        "root. Returns the file contents. Use this to inspect source code, "
        "configs, READMEs, etc. before editing or answering questions about them."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file, relative to the workspace root.",
            },
            "offset": {
                "type": "integer",
                "description": "Optional 1-indexed line to start reading from.",
                "default": 1,
            },
            "limit": {
                "type": "integer",
                "description": "Optional max number of lines to read.",
                "default": 2000,
            },
        },
        "required": ["path"],
    }

    def run(self, path: str, offset: int = 1, limit: int = 2000) -> ToolResult:
        p = _resolve(path)
        if not p.exists():
            return ToolResult(output=f"File not found: {path}", error=True)
        if not p.is_file():
            return ToolResult(output=f"Not a file: {path}", error=True)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return ToolResult(output=f"Read failed: {exc}", error=True)
        lines = text.splitlines()
        start = max(0, offset - 1)
        end = start + limit
        chunk = "\n".join(lines[start:end])
        out = (
            f"File: {path} ({len(lines)} lines total)\n"
            f"Showing lines {start + 1}–{min(end, len(lines))}\n\n"
            f"{_truncate(chunk)}"
        )
        return ToolResult(output=out, metadata={"path": str(p), "lines": len(lines)})


# --------------------------------------------------------------------------- #
# write_file
# --------------------------------------------------------------------------- #


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Create or overwrite a UTF-8 text file with the given contents. "
        "Parent directories are created automatically. Use `edit_file` instead "
        "when you only want to change part of an existing file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to write to."},
            "content": {"type": "string", "description": "Full file contents."},
        },
        "required": ["path", "content"],
    }
    requires_confirmation = True

    def run(self, path: str, content: str) -> ToolResult:
        p = _resolve(path)
        if not _is_path_safe(p):
            return ToolResult(
                output=f"Refusing to write outside workspace: {path}", error=True
            )
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        except Exception as exc:
            return ToolResult(output=f"Write failed: {exc}", error=True)
        out = f"Wrote {len(content):,} chars to {path}"
        return ToolResult(output=out, metadata={"path": str(p), "bytes": len(content)})


# --------------------------------------------------------------------------- #
# edit_file
# --------------------------------------------------------------------------- #


class EditFileTool(Tool):
    name = "edit_file"
    description = (
        "Apply a single find-and-replace to an existing UTF-8 text file. "
        "If `old_text` appears exactly once it is replaced with `new_text`. "
        "If it appears multiple times you must supply more surrounding context "
        "to disambiguate, or set `replace_all=true` to replace every occurrence."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to edit."},
            "old_text": {
                "type": "string",
                "description": "Exact text to find (must match whitespace exactly).",
            },
            "new_text": {"type": "string", "description": "Replacement text."},
            "replace_all": {
                "type": "boolean",
                "description": "If true, replace every occurrence.",
                "default": False,
            },
        },
        "required": ["path", "old_text", "new_text"],
    }
    requires_confirmation = True

    def run(
        self,
        path: str,
        old_text: str,
        new_text: str,
        replace_all: bool = False,
    ) -> ToolResult:
        p = _resolve(path)
        if not p.exists():
            return ToolResult(output=f"File not found: {path}", error=True)
        if not _is_path_safe(p):
            return ToolResult(
                output=f"Refusing to edit outside workspace: {path}", error=True
            )
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return ToolResult(output=f"Read failed: {exc}", error=True)

        count = text.count(old_text)
        if count == 0:
            return ToolResult(
                output=(
                    "old_text not found in file. Tip: match whitespace exactly, "
                    "or use `read_file` first to see the actual contents."
                ),
                error=True,
            )
        if count > 1 and not replace_all:
            return ToolResult(
                output=(
                    f"old_text appears {count} times — either provide more "
                    "surrounding context to disambiguate, or set replace_all=true."
                ),
                error=True,
            )

        new_full = text.replace(old_text, new_text) if replace_all else (
            text.replace(old_text, new_text, 1)
        )
        try:
            p.write_text(new_full, encoding="utf-8")
        except Exception as exc:
            return ToolResult(output=f"Write failed: {exc}", error=True)

        # Build a tiny unified-diff-style preview
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        diff = []
        for ln in old_lines[:8]:
            diff.append(f"- {ln}")
        for ln in new_lines[:8]:
            diff.append(f"+ {ln}")
        if len(old_lines) > 8 or len(new_lines) > 8:
            diff.append("… (truncated)")
        diff_text = "\n".join(diff) if diff else "(no textual change)"

        out = (
            f"Edited {path}: replaced {count if replace_all else 1} occurrence(s).\n"
            f"Diff preview:\n{diff_text}"
        )
        return ToolResult(
            output=out,
            metadata={
                "path": str(p),
                "occurrences_replaced": count if replace_all else 1,
            },
        )


# --------------------------------------------------------------------------- #
# list_directory
# --------------------------------------------------------------------------- #


class ListDirectoryTool(Tool):
    name = "list_directory"
    description = (
        "List the contents of a directory relative to the workspace root. "
        "Returns one entry per line, with a trailing `/` for directories. "
        "Hidden files (starting with `.`) are included unless `include_hidden=false`."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to list. Defaults to workspace root.",
                "default": ".",
            },
            "include_hidden": {
                "type": "boolean",
                "description": "Include dotfiles.",
                "default": True,
            },
            "recursive": {
                "type": "boolean",
                "description": "Recurse into subdirectories.",
                "default": False,
            },
        },
    }

    def run(
        self,
        path: str = ".",
        include_hidden: bool = True,
        recursive: bool = False,
    ) -> ToolResult:
        p = _resolve(path)
        if not p.exists():
            return ToolResult(output=f"Directory not found: {path}", error=True)
        if not p.is_dir():
            return ToolResult(output=f"Not a directory: {path}", error=True)
        if not _is_path_safe(p):
            return ToolResult(
                output=f"Refusing to list outside workspace: {path}", error=True
            )
        entries: list[str] = []
        if recursive:
            for root, dirs, files in os.walk(p):
                # prune hidden dirs if needed
                if not include_hidden:
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                rel_root = os.path.relpath(root, p)
                prefix = "" if rel_root == "." else rel_root + "/"
                for name in sorted(dirs + files):
                    if not include_hidden and name.startswith("."):
                        continue
                    full = os.path.join(root, name)
                    is_dir = os.path.isdir(full)
                    entries.append(f"{prefix}{name}{'/' if is_dir else ''}")
        else:
            for name in sorted(os.listdir(p)):
                if not include_hidden and name.startswith("."):
                    continue
                full = p / name
                is_dir = full.is_dir()
                entries.append(f"{name}{'/' if is_dir else ''}")
        out = (
            f"Directory: {path} ({len(entries)} entries)\n\n"
            + "\n".join(entries)
        )
        return ToolResult(output=_truncate(out, 50_000), metadata={"path": str(p)})


# --------------------------------------------------------------------------- #
# read_many_files
# --------------------------------------------------------------------------- #


class ReadManyFilesTool(Tool):
    name = "read_many_files"
    description = (
        "Read many files at once, matched by glob patterns. Returns each file "
        "with a header showing its path. Great for getting a quick overview of "
        "a small project. Respects `.gitignore`-style exclusions via the "
        "`exclude` patterns."
    )
    parameters = {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Glob patterns, e.g. [\"src/**/*.py\"].",
            },
            "exclude": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Glob patterns to exclude.",
                "default": [],
            },
            "max_files": {
                "type": "integer",
                "description": "Hard cap on number of files read.",
                "default": 50,
            },
        },
        "required": ["paths"],
    }

    def run(
        self,
        paths: list[str],
        exclude: Optional[list[str]] = None,
        max_files: int = 50,
    ) -> ToolResult:
        exclude = exclude or []
        root = workspace_root()
        matched: list[Path] = []
        for pattern in paths:
            for p in root.glob(pattern):
                if not p.is_file():
                    continue
                if any(p.match(ex) for ex in exclude):
                    continue
                matched.append(p)
        # de-dup, sort, cap
        seen = set()
        uniq: list[Path] = []
        for p in matched:
            rp = p.resolve()
            if rp in seen:
                continue
            seen.add(rp)
            uniq.append(p)
        uniq = sorted(uniq)[:max_files]

        if not uniq:
            return ToolResult(
                output=f"No files matched patterns {paths} (excluded {exclude}).",
                error=False,
            )
        chunks: list[str] = []
        for p in uniq:
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                chunks.append(f"\n=== {p} (read failed: {exc}) ===\n")
                continue
            chunks.append(f"\n=== {p} ===\n{content}\n")
        return ToolResult(
            output=_truncate("".join(chunks), 200_000),
            metadata={"count": len(uniq), "files": [str(p) for p in uniq]},
        )


# --------------------------------------------------------------------------- #
# run_shell
# --------------------------------------------------------------------------- #


# Commands the agent is never allowed to run without explicit user approval.
_DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\s+/",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r":\(\)\s*\{",  # fork bomb
    r"\bgit\s+push\s+--force\b",
    r"\bsudo\b",
]


class RunShellTool(Tool):
    name = "run_shell"
    description = (
        "Run a shell command in the workspace root and return stdout+stderr. "
        "Use this for running tests, git, build tools, ls, etc. Avoid "
        "long-running commands; they will be killed after the timeout."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute."},
            "timeout": {
                "type": "integer",
                "description": "Max seconds to wait.",
                "default": 60,
            },
            "cwd": {
                "type": "string",
                "description": "Working directory (defaults to workspace root).",
                "default": ".",
            },
        },
        "required": ["command"],
    }
    requires_confirmation = True

    def run(self, command: str, timeout: int = 60, cwd: str = ".") -> ToolResult:
        for pat in _DANGEROUS_PATTERNS:
            if re.search(pat, command):
                return ToolResult(
                    output=(
                        f"Refusing to run potentially dangerous command (matched "
                        f"pattern {pat!r}): {command}. The user must run this "
                        "themselves."
                    ),
                    error=True,
                )
        work_dir = _resolve(cwd)
        if not _is_path_safe(work_dir):
            return ToolResult(
                output=f"Refusing to run shell outside workspace: {cwd}",
                error=True,
            )
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                output=f"Command timed out after {timeout}s: {command}",
                error=True,
            )
        except Exception as exc:
            return ToolResult(output=f"Spawn failed: {exc}", error=True)

        out = (
            f"$ {command}\n"
            f"(exit code {proc.returncode})\n"
            f"--- stdout ---\n{proc.stdout}\n"
            f"--- stderr ---\n{proc.stderr}"
        )
        return ToolResult(
            output=_truncate(out, 100_000),
            metadata={
                "exit_code": proc.returncode,
                "stdout_len": len(proc.stdout),
                "stderr_len": len(proc.stderr),
            },
        )


# --------------------------------------------------------------------------- #
# web_fetch
# --------------------------------------------------------------------------- #


class WebFetchTool(Tool):
    name = "web_fetch"
    description = (
        "Fetch a URL and return its text content (HTML is converted to "
        "Markdown-friendly text). Use this to read docs, articles, or API "
        "responses that don't need grounding."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "HTTP(S) URL to fetch."},
            "max_chars": {
                "type": "integer",
                "description": "Cap on returned text length.",
                "default": 50000,
            },
        },
        "required": ["url"],
    }

    def run(self, url: str, max_chars: int = 50000) -> ToolResult:
        try:
            import httpx
            from bs4 import BeautifulSoup
            import html2text
        except ImportError as exc:
            return ToolResult(
                output=(
                    "Missing optional dependency for web_fetch. "
                    "Run: pip install httpx beautifulsoup4 html2text\n"
                    f"Original error: {exc}"
                ),
                error=True,
            )
        try:
            with httpx.Client(timeout=20, follow_redirects=True) as client:
                resp = client.get(
                    url,
                    headers={"User-Agent": "gemini-cli-py/1.0 (+web_fetch tool)"},
                )
                resp.raise_for_status()
        except Exception as exc:
            return ToolResult(output=f"Fetch failed: {exc}", error=True)
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type.lower():
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            h = html2text.HTML2Text()
            h.body_width = 0  # don't wrap
            h.ignore_links = False
            text = h.handle(str(soup))
        else:
            text = resp.text
        out = f"URL: {url}\nContent-Type: {content_type}\n\n{_truncate(text, max_chars)}"
        return ToolResult(output=out, metadata={"url": url, "status": resp.status_code})


# --------------------------------------------------------------------------- #
# google_search (grounded)
# --------------------------------------------------------------------------- #


class GoogleSearchTool(Tool):
    name = "google_search"
    description = (
        "Search the web using Google Search grounding. Returns a short answer "
        "plus supporting search results with URLs. Use this for any question "
        "that needs current information (news, latest docs, package versions, "
        "sports scores, etc.)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
        },
        "required": ["query"],
    }

    def __init__(self, client=None):
        self._client = client  # injected GeminiClient

    def run(self, query: str) -> ToolResult:
        if self._client is None:
            return ToolResult(
                output="Google Search not configured (no Gemini client).",
                error=True,
            )
        try:
            from google.genai import types

            # Use the search tool via generate_content
            cfg = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            )
            resp = self._client.client.models.generate_content(
                model=self._client._settings.model,
                contents=query,
                config=cfg,
            )
        except Exception as exc:
            return ToolResult(output=f"Google Search failed: {exc}", error=True)

        # Extract text + grounding metadata
        text = ""
        try:
            text = resp.text or ""
        except Exception:
            text = ""
        citations: list[str] = []
        try:
            meta = resp.candidates[0].grounding_metadata
            if meta and getattr(meta, "grounding_chunks", None):
                for chunk in meta.grounding_chunks:
                    web = getattr(chunk, "web", None)
                    if web and getattr(web, "uri", None):
                        citations.append(f"{web.uri} — {getattr(web, 'title', '')}")
        except Exception:
            pass
        out = text
        if citations:
            out += "\n\nSources:\n" + "\n".join(f"- {c}" for c in citations[:8])
        return ToolResult(
            output=_truncate(out, 30_000),
            metadata={"query": query, "citation_count": len(citations)},
        )


# --------------------------------------------------------------------------- #
# glob
# --------------------------------------------------------------------------- #


class GlobTool(Tool):
    name = "glob"
    description = (
        "Find files matching a glob pattern (e.g. `**/*.py`). Returns the list "
        "of matching paths, one per line."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern, e.g. `src/**/*.py`.",
            },
            "path": {
                "type": "string",
                "description": "Base directory to search from.",
                "default": ".",
            },
        },
        "required": ["pattern"],
    }

    def run(self, pattern: str, path: str = ".") -> ToolResult:
        base = _resolve(path)
        if not base.exists():
            return ToolResult(output=f"Base dir not found: {path}", error=True)
        try:
            matches = sorted(str(p.relative_to(workspace_root())) for p in base.glob(pattern))
        except Exception as exc:
            return ToolResult(output=f"Glob failed: {exc}", error=True)
        if not matches:
            return ToolResult(
                output=f"No files matched: {pattern}", metadata={"count": 0}
            )
        out = f"Pattern: {pattern}\nMatches ({len(matches)}):\n" + "\n".join(matches)
        return ToolResult(
            output=_truncate(out, 30_000),
            metadata={"count": len(matches), "files": matches},
        )


# --------------------------------------------------------------------------- #
# ask_user
# --------------------------------------------------------------------------- #


class AskUserTool(Tool):
    """
    Tool that pauses the agent loop and asks the user a question. The agent
    loop is responsible for actually surfacing this to the UI and waiting for
    a response — this class just packages the question.
    """

    name = "ask_user"
    description = (
        "Ask the user a clarifying question. Use this when you're missing "
        "information needed to proceed (e.g. which file to edit, which "
        "framework they prefer, whether to apply a risky change). The user's "
        "answer will be returned as the tool result."
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user.",
            },
        },
        "required": ["question"],
    }

    def run(self, question: str) -> ToolResult:
        # The agent loop intercepts this tool and routes it to the UI. If we
        # actually get here it means nobody intercepted — return a placeholder.
        return ToolResult(
            output="(interactive ask_user was not intercepted by the UI)",
            error=True,
        )
