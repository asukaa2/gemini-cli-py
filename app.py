#!/usr/bin/env python3
"""
Gemini CLI — Python + Gradio Edition.

Entry point: `python app.py` starts a Gradio server on http://localhost:7860.

This is a Python port of Google's https://github.com/google-gemini/gemini-cli,
rewritten to use the official `google-genai` Python SDK and a Gradio web UI
instead of an Ink terminal UI.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _load_dotenv() -> None:
    """Load .env from CWD if python-dotenv is available."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="gemini-cli-py",
        description="Python + Gradio port of google-gemini/gemini-cli",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=7860, help="Port to bind (default: 7860)"
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="Create a public Gradio share link (*.gradio.live) at launch time. "
        "You can also enable sharing from inside the running UI via the "
        "'🌐 Public URL' panel.",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory (default: current dir)",
    )
    args = parser.parse_args()

    _load_dotenv()

    if args.workspace:
        os.environ["GEMINI_WORKSPACE"] = str(Path(args.workspace).resolve())

    # Import after .env is loaded so env vars are visible
    from gemini_py.ui import launch

    # If --share is passed, the share URL is captured inside launch() and
    # surfaced in the running UI's "🌐 Public URL" panel automatically.
    # If --share is NOT passed, the user can still click the in-UI
    # "🌐 Enable public URL" button to spawn a sibling share process.
    launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        show_error=True,
        inbrowser=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
