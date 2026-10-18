# langchain-playground

## Running the 02-hitl-example demo

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14+.

```bash
cd 02-hitl-example
cp .env.example .env   # then set OPENAI_API_KEY
./run-demo.sh
```

This starts the MCP server (`01-example-mcp-server`), the HITL API, and the Streamlit UI. Open http://localhost:8501 in your browser. Press Ctrl+C to stop everything.
