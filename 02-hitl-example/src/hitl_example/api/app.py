"""FastAPI app factory and entry point."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.language_models import BaseChatModel

from hitl_example.agent import build_agent
from hitl_example.api.routes import router
from hitl_example.constants import API_HOST, API_PORT, CORS_ORIGINS, MODEL


def create_app(model: str | BaseChatModel = MODEL) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Load the MCP tools once at startup and share one agent across requests.
        # Its InMemorySaver keeps paused runs only while this process lives; use a
        # Sqlite/Postgres checkpointer for anything real.
        app.state.agent = await build_agent(model)
        yield

    app = FastAPI(title="HITL example", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


def main():
    uvicorn.run(create_app(), host=API_HOST, port=API_PORT)


if __name__ == "__main__":
    main()
