# langchain-playground

## Running the 02-hitl-example demo

### Installation

Install [uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

The demo uses two projects, each with its own virtual environment. Install the Python version and dependencies for both:

```bash
uv python install 3.14
uv sync --directory 01-example-mcp-server
uv sync --directory 02-hitl-example
```

Then configure the environment:

```bash
cp 02-hitl-example/.env.example 02-hitl-example/.env   # then set OPENAI_API_KEY
```

### Running

```bash
./02-hitl-example/run-demo.sh
```

This starts the MCP server (`01-example-mcp-server`), the HITL API, and the Streamlit UI. Open http://localhost:8501 in your browser. Press Ctrl+C to stop everything.
