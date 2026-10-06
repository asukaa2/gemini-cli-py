# Gemini CLI — Python + Gradio Edition

A from-scratch Python port of Google's [gemini-cli](https://github.com/google-gemini/gemini-cli)
rewritten to use the official [`google-genai`](https://pypi.org/project/google-genai/)
Python SDK and a [Gradio](https://gradio.app) web UI instead of the original
TypeScript + Ink terminal UI.

This is **not** a line-by-line port — the original repo is a large TypeScript
monorepo (`packages/cli`, `packages/core`, `packages/sdk`, `packages/a2a-server`,
`packages/devtools`, `packages/vscode-ide-companion`) with hundreds of files
covering terminal UI, node-pty sandboxing, MCP server hosting, A2A protocol,
VSCode integration, telemetry, billing, and more. Many of those subsystems
are deeply tied to the JS/TS ecosystem and either make no sense in Python
(terminal TUI, node-pty) or already have good Python equivalents (MCP client
via the `mcp` package, telemetry via OpenTelemetry).

Instead, this port captures the **core agent loop**: chat with Gemini, call
tools (read/write/edit files, list dirs, run shell, web fetch, Google Search
grounding, glob, ask_user), persist conversation sessions, and inspect the
workspace side-by-side — all in a clean two-pane Gradio UI.

## ✨ Features

| Feature | Status | Notes |
|---|---|---|
| Chat with Gemini (streaming) | ✅ | via `google-genai` |
| Tool calling (function calls) | ✅ | agent loop with up to N tool iterations per turn |
| `read_file`, `write_file`, `edit_file` | ✅ | with workspace sandboxing |
| `list_directory` (recursive option) | ✅ | |
| `read_many_files` (glob) | ✅ | respects exclude patterns |
| `run_shell` | ✅ | with dangerous-command blocklist + timeout |
| `web_fetch` | ✅ | HTML → Markdown via `html2text` |
| `google_search` (grounded) | ✅ | via Gemini's Google Search tool |
| `glob` | ✅ | |
| `ask_user` | ⚠️ stub | the agent loop can route this to the UI; currently a placeholder |
| MCP client (stdio servers) | ✅ | connect to existing MCP servers, expose their tools |
| JSON session persistence | ✅ | `~/.gemini-py/sessions/*.json` |
| Markdown rendering in chat | ✅ | Gradio's `render_markdown` |
| File upload (images + PDF) | ✅ | sent as `inline_data` parts |
| Tool-call cards | ✅ | collapsible bordered cards in chat |
| Two-pane layout (chat + workspace) | ✅ | file tree + viewer on the right |
| Approval flow for risky tools | ⚠️ partial | `requires_confirmation` flag is set; UI gate is a TODO |
| OAuth login | ❌ | API key only (by design — see "Auth" below) |
| Sandbox (seatbelt / bwrap) | ❌ | Python's `subprocess` only |
| Skills, hooks, plan mode | ❌ | not ported from the TS version |
| Telemetry, billing | ❌ | not ported |
| Browser agent (Puppeteer) | ❌ | not ported |
| VSCode companion | ❌ | N/A |

## 🚀 Quick start

### 1. Get an API key

Go to <https://aistudio.google.com/apikey> and create a key (free tier: 1000
requests/day with Gemini 2.5).

### 2. Install dependencies

```bash
cd gemini-cli-py
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set your API key

Either export it as an env var:

```bash
export GEMINI_API_KEY="your-key-here"
```

…or copy `.env.example` to `.env` and fill it in:

```bash
cp .env.example .env
# edit .env
```

…or just paste it into the Settings panel in the UI after launch.

### 4. Run

```bash
python app.py
```

Open <http://localhost:7860> in your browser.

### CLI flags

```
python app.py --help
python app.py --port 8080          # custom port
python app.py --share              # create a public Gradio share link
python app.py --workspace /path    # pin the workspace root
```

## 🏗 Architecture

```
gemini-cli-py/
├── app.py                       # Entrypoint — launches Gradio
├── requirements.txt
├── .env.example
├── README.md
└── gemini_py/
    ├── __init__.py
    ├── config.py                # Settings, paths, model registry
    ├── client.py                # GeminiClient — wraps google-genai SDK
    ├── tools/
    │   ├── __init__.py          # build_default_registry()
    │   ├── base.py              # Tool ABC + ToolRegistry + ToolResult
    │   └── builtin.py           # 10 built-in tools
    ├── agents/
    │   ├── __init__.py
    │   └── loop.py              # AgentLoop — streams AgentEvents
    ├── sessions/
    │   ├── __init__.py
    │   └── manager.py           # JSON-backed SessionStore
    ├── mcp/
    │   ├── __init__.py
    │   └── client.py            # MCPManager — connects to stdio MCP servers
    └── ui/
        ├── __init__.py
        └── app.py               # Gradio Blocks two-pane UI
```

### How the agent loop works

1. The user submits a message. It's appended to the session's `messages` list.
2. `AgentLoop.run()` converts the message list to the SDK's `contents`
   shape, attaches the tool declarations from the registry, and calls
   `client.stream(...)`.
3. As chunks arrive, text deltas are streamed back to the UI.
4. When the model emits a `function_call` part, the loop looks up the tool
   by name in the registry, calls `tool.safe_run(args)`, and appends a
   `tool` message to the history with the result.
5. The loop repeats (up to `max_iterations` times per turn) until the model
   stops calling tools.

### How sessions work

Every conversation has a 12-char hex id and lives at
`~/.gemini-py/sessions/<id>.json`. The file contains the full message history
including tool calls, the model used, and timestamps. The dropdown in the
UI lets you switch / delete / create sessions freely.

### How MCP works

If `enable_mcp=true` (toggle in Settings) and the `mcp` package is installed,
clicking **🔌 Connect MCP servers** will spawn each configured server as a
subprocess, list its tools, and register each as a wrapped `Tool` in the
registry under the name `mcp_<server>_<tool>`. Configure servers via the
`GEMINI_MCP_SERVERS` env var (semicolon- or newline-separated command lines)
or via the `mcp_servers` list in `~/.gemini-py/settings.json`.

## 🔧 Customizing

### Add a new built-in tool

```python
# gemini_py/tools/my_tool.py
from .base import Tool, ToolResult

class MyTool(Tool):
    name = "my_tool"
    description = "Does the thing."
    parameters = {
        "type": "object",
        "properties": {"x": {"type": "integer"}},
        "required": ["x"],
    }

    def run(self, x: int) -> ToolResult:
        return ToolResult(output=f"x squared = {x*x}")
```

Then register it in `gemini_py/tools/__init__.py::build_default_registry()`.

### Change the system prompt

Either edit it in the Settings panel (persists to `settings.json`), or edit
`DEFAULT_SYSTEM_PROMPT` in `gemini_py/config.py`.

### Pin a different default model

Set `GEMINI_MODEL=gemini-2.5-pro` in your environment, or change
`DEFAULT_MODEL_ID` in `gemini_py/config.py`.

## 🔐 Auth model

Only API-key auth is supported (by design — the original's OAuth flow requires
a Google client ID and a callback server, which is overkill for a personal
dev tool). The key can come from:

1. `GEMINI_API_KEY` env var (highest precedence)
2. `~/.gemini-py/settings.json` (saved by the Settings panel)
3. `.env` file in CWD (loaded by `python-dotenv`)

## 📋 What was NOT ported (and why)

| Subsystem | Reason |
|---|---|
| Ink terminal TUI | Replaced by Gradio web UI — the whole point of this port |
| `node-pty` shell sandbox | Python's `subprocess` is fine; OS-level sandbox (seatbelt/bwrap) is out of scope |
| OAuth login | API key only — see "Auth model" |
| Hooks system | Would require a YAML/TOML config schema; can be added later |
| Skills system | Same — heavy config-driven feature, deferred |
| Plan mode | UI affordance only; can be added later |
| Browser agent (Puppeteer) | Use Playwright in Python if needed — out of scope here |
| A2A server | A separate protocol; not relevant to the chat UX |
| VSCode companion | N/A — Gradio is browser-based |
| Telemetry / billing | Internal Google infra; not applicable |
| Checkpointing | Sessions JSON store covers the resume use case |
| Context compression / token accounting | Gemini's API handles context window truncation server-side for 2.x models |

## 📄 License

Apache 2.0, same as the original `google-gemini/gemini-cli`. The original
project is © Google LLC. This Python port is an independent implementation
that uses the same public Gemini API.

## 🙏 Acknowledgments

- The [gemini-cli](https://github.com/google-gemini/gemini-cli) team for the
  original design and toolset.
- The [google-genai](https://github.com/googleapis/python-genai) Python SDK team.
- The [Gradio](https://github.com/gradio-app/gradio) team for the UI framework.
