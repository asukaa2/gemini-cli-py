#!/usr/bin/env python3
"""
Gemini CLI — Python + Gradio Edition.

Entry point: `python app.py` starts a Gradio server on http://localhost:7860.

This is a Python port of Google's https://github.com/google-gemini/gemini-cli,
rewritten to use the official `google-genai` Python SDK and a Gradio web UI
instead of an Ink terminal UI.
"""

from __future__ import annotations
from theme.dark import *
import argparse
import os
import sys
from pathlib import Path


theme = Dark()


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
        "Gradio prints the URL to stdout.",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory (default: current dir)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Gemini API key (overrides GEMINI_API_KEY env var)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Gemini model name (overrides GEMINI_MODEL env var)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature (overrides GEMINI_TEMPERATURE env var)",
    )
    args = parser.parse_args()

    if args.workspace:
        os.environ["GEMINI_WORKSPACE"] = str(Path(args.workspace).resolve())

    if args.api_key:
        os.environ["GEMINI_API_KEY"] = args.api_key

    if args.model:
        os.environ["GEMINI_MODEL"] = args.model

    if args.temperature is not None:
        os.environ["GEMINI_TEMPERATURE"] = str(args.temperature)

    # Import after CLI args are parsed so env vars are visible
    from gemini_py.ui import launch

    # Pass --share through to Gradio's native share feature. The resulting
    # *.gradio.live URL is printed to stdout by Gradio itself.
    launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        show_error=True,
        inbrowser=False,
        theme=theme, 
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
