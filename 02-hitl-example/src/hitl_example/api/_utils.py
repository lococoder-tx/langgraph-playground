"""Private helpers for the routes."""

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

import jsonschema
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from langchain.agents.middleware import InputAgentState
from langchain_core.messages import AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from hitl_example.agent import Agent
from hitl_example.api.schemas import (
    Accept,
    Answer,
    ElicitationInterrupt,
    FormRequest,
    InvokeResult,
    Message,
    PendingInterrupt,
    Resume,
    SendMessage,
)

logger = logging.getLogger(__name__)


def thread_config(thread_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}}


def user_message(body: SendMessage) -> InputAgentState:
    return {"messages": [HumanMessage(body.content, id=str(uuid.uuid4()))]}


async def pending_interrupts(agent: Agent, thread_id: str) -> list[PendingInterrupt]:
    state = await agent.aget_state(thread_config(thread_id))
    # Validating coerces each raw interrupt dict into the typed model.
    return [
        PendingInterrupt.model_validate({"id": i.id, "value": i.value})
        for i in state.interrupts
    ]


async def ensure_no_pending_interrupts(agent: Agent, thread_id: str) -> None:
    """Refuse new input while a tool is paused waiting for the user.

    New input now would leave the paused tool call unanswered in the history,
    which the model provider rejects. Answer it first.
    """
    if pending := await pending_interrupts(agent, thread_id):
        raise HTTPException(
            409,
            {
                "message": "Thread has pending interrupts; resume them first.",
                "interrupts": [i.model_dump() for i in pending],
            },
        )


async def build_resume_command(agent: Agent, thread_id: str, body: Resume) -> Command:
    """Find the interrupt being answered, check the answers, and build the resume."""
    interrupt = await find_interrupt(agent, thread_id, body.interrupt_id)
    validate_answers(interrupt=interrupt.value, answers=body.responses)
    return resume_command(interrupt.id, body.responses)


async def find_interrupt(
    agent: Agent, thread_id: str, interrupt_id: str
) -> PendingInterrupt:
    for interrupt in await pending_interrupts(agent, thread_id):
        if interrupt.id == interrupt_id:
            return interrupt
    raise HTTPException(404, "No pending interrupt with that id.")


def validate_answers(
    interrupt: ElicitationInterrupt, answers: dict[str, Answer]
) -> None:
    """Check the browser's answers against what the MCP tool asked for.

    `langchain.mcp` only checks that each key is answered with a valid action; it
    doesn't validate `content` against the schema, so do it here.
    """
    asked = {r.key: r for r in interrupt.requests}
    if answers.keys() != asked.keys():
        raise HTTPException(422, f"Expected answers for exactly: {sorted(asked)}")

    for key, answer in answers.items():
        request = asked[key]
        if isinstance(answer, Accept) and isinstance(request, FormRequest):
            try:
                jsonschema.validate(answer.content or {}, request.requested_schema)
            except jsonschema.ValidationError as e:
                raise HTTPException(422, f"{key}: {e.message}") from e


def resume_command(interrupt_id: str, answers: dict[str, Answer]) -> Command:
    """Build the resume value `langchain.mcp` expects for an elicitation interrupt.

    Keyed by interrupt id so it works when several tools paused in one turn.
    """
    responses = {key: a.model_dump(exclude_none=True) for key, a in answers.items()}
    return Command(resume={interrupt_id: {"responses": responses}})


async def invoke_turn(
    agent: Agent, thread_id: str, input: InputAgentState | Command
) -> InvokeResult:
    """Run the agent to completion (or its next interrupt) and return the result."""
    config = thread_config(thread_id)
    before = await agent.aget_state(config)
    seen = len(before.values.get("messages", []))

    # version="v2" returns a GraphOutput with `.value` (the state) and `.interrupts`.
    result = await agent.ainvoke(input, config, version="v2")

    messages = [_to_message(m) for m in result.value["messages"][seen:]]
    interrupts = [
        PendingInterrupt.model_validate({"id": i.id, "value": i.value})
        for i in result.interrupts
    ]
    last = messages[-1] if messages else None
    reply = last.content if last and last.type == "ai" and not interrupts else None
    return InvokeResult(messages=messages, reply=reply, interrupts=interrupts)


def _to_message(message: AnyMessage) -> Message:
    return Message(
        id=message.id,
        type=message.type,
        content=str(message.text),
        tool_calls=getattr(message, "tool_calls", []),
        tool_call_id=getattr(message, "tool_call_id", None),
    )


def ndjson_response(events: AsyncIterator[Any]) -> StreamingResponse:
    """Stream events to the client as newline-delimited JSON."""

    async def lines():
        try:
            async for event in events:
                yield json.dumps(event, default=str) + "\n"
        except Exception:
            # Headers (and a 200) are already sent, so report failures in-band.
            logger.exception("Agent run failed")
            yield json.dumps({"type": "error", "message": "Agent run failed."}) + "\n"

    return StreamingResponse(
        lines(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
