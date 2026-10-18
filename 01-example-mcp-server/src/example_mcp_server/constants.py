import os
from typing import cast, get_args

from dotenv import load_dotenv
from fastmcp.server.server import Transport

# have to use get_args here since each value in transport literal is a type
TRANSPORT_TYPES = get_args(Transport)


def _parse_transport(value: str) -> Transport:
    print(TRANSPORT_TYPES)
    if value not in TRANSPORT_TYPES:
        raise ValueError(
            f"Unsupported MCP_TRANSPORT {value!r}; expected one of {TRANSPORT_TYPES}"
        )
    return cast(Transport, value)


# Searches upward from this file for a .env; existing environment variables take precedence.
load_dotenv()

SERVER_NAME = os.getenv("MCP_SERVER_NAME", "example-mcp-server")
TRANSPORT = _parse_transport(os.getenv("MCP_TRANSPORT", "streamable-http"))

HOST = os.getenv("MCP_HOST", "127.0.0.1")
PORT = int(os.getenv("MCP_PORT", "8000"))
