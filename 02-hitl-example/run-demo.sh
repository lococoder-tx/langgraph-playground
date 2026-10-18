#!/usr/bin/env bash
# Runs the MCP server, the HITL API and the Streamlit UI. Ctrl+C stops all three.
set -e
cd "$(dirname "$0")"
trap 'kill 0' EXIT
# Each project uses its own .venv; an activated one only makes uv warn.
unset VIRTUAL_ENV

uv run --directory ../01-example-mcp-server example-mcp-server &
# hitl-server loads the MCP tools at startup, so the MCP server must be up first.
until curl -s localhost:8000 >/dev/null; do sleep 0.5; done

uv run hitl-server &
# headless skips Streamlit's first-run email prompt; open http://localhost:8501 yourself.
uv run streamlit run src/hitl_example/ui.py --server.headless true
