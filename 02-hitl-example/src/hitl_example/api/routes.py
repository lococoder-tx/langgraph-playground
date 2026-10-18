"""Endpoints for chatting on a thread and answering its interrupts."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from hitl_example.agent import Agent
from hitl_example.api._utils import (
    build_resume_command,
    ensure_no_pending_interrupts,
    invoke_turn,
    ndjson_response,
    pending_interrupts,
    thread_config,
    user_message,
)
from hitl_example.api.schemas import (
    InvokeResult,
    PendingInterrupt,
    Resume,
    SendMessage,
    Thread,
)
from hitl_example.events import stream_events

router = APIRouter(prefix="/threads", tags=["threads"])


def get_agent(request: Request) -> Agent:
    return request.app.state.agent


AgentDep = Annotated[Agent, Depends(get_agent)]


@router.post("")
async def create_thread() -> Thread:
    return Thread(thread_id=str(uuid.uuid4()))


@router.get("/{thread_id}/interrupts")
async def list_interrupts(thread_id: str, agent: AgentDep) -> list[PendingInterrupt]:
    """Pending interrupts, e.g. to re-render the form after a page reload."""
    return await pending_interrupts(agent, thread_id)


@router.post("/{thread_id}/messages")
async def send_message(
    thread_id: str, body: SendMessage, agent: AgentDep
) -> StreamingResponse:
    """Send a user message and stream the agent's turn as NDJSON."""
    await ensure_no_pending_interrupts(agent, thread_id)
    config = thread_config(thread_id)
    return ndjson_response(stream_events(agent, config, user_message(body)))


@router.post("/{thread_id}/messages/invoke")
async def send_message_invoke(
    thread_id: str, body: SendMessage, agent: AgentDep
) -> InvokeResult:
    """Send a user message and return the agent's whole turn at once."""
    await ensure_no_pending_interrupts(agent, thread_id)
    return await invoke_turn(agent, thread_id, user_message(body))


@router.post("/{thread_id}/resume")
async def resume(thread_id: str, body: Resume, agent: AgentDep) -> StreamingResponse:
    """Answer a pending interrupt and stream the rest of the run as NDJSON."""
    command = await build_resume_command(agent, thread_id, body)
    return ndjson_response(stream_events(agent, thread_config(thread_id), command))


@router.post("/{thread_id}/resume/invoke")
async def resume_invoke(thread_id: str, body: Resume, agent: AgentDep) -> InvokeResult:
    """Answer a pending interrupt and return the rest of the run at once."""
    command = await build_resume_command(agent, thread_id, body)
    return await invoke_turn(agent, thread_id, command)
