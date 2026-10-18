import os

from dotenv import load_dotenv

# Searches upward from this file for a .env; existing environment variables take precedence.
load_dotenv()

MODEL = os.getenv("MODEL", "openai:gpt-6-luna")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")

# FastAPI backend (port 8000 is taken by the MCP server)
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8001"))
# Comma-separated browser origins allowed to call the API
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")
