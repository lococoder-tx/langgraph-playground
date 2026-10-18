"""Turn one agent run into a flat stream of JSON-serializable events."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Literal, TypedDict

from langchain.agents.middleware import InputAgentState
from langchain.mcp.elicitation import MCPElicitationInterrupt
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from hitl_example.agent import Agent, _as_text


class TextEvent(TypedDict):
    type: Literal["text"]
    delta: str


class TextEndEvent(TypedDict):
    type: Literal["text_end"]


class ToolCallEvent(TypedDict):
    type: Literal["tool_call"]
    id: str
    name: str
    input: Any


class ToolResultEvent(TypedDict):
    type: Literal["tool_result"]
    id: str
    output: str


class ToolErrorEvent(TypedDict):
    type: Literal["tool_error"]
    id: str
    error: str


class InterruptEvent(TypedDict):
    type: Literal["interrupt"]
    id: str
    value: MCPElicitationInterrupt


type AgentEvent = (
    TextEvent
    | TextEndEvent
    | ToolCallEvent
    | ToolResultEvent
    | ToolErrorEvent
    | InterruptEvent
)


async def stream_events(
    agent: Agent, config: RunnableConfig, input: InputAgentState | Command
) -> AsyncIterator[AgentEvent]:
    """Run the agent and yield its events as they happen.

    `input` is either new state (`{"messages": [...]}`) or a `Command(resume=...)`
    answering a pending interrupt. Any interrupts the run stops on are yielded last.
    """
    stream = await agent.astream_events(input, config, version="v3")
    # Exiting the block aborts the run, e.g. if the HTTP client disconnects.
    async with stream:
        queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()

        async def consume_messages():
            async for message in stream.messages:
                has_text = False
                async for delta in message.text:
                    has_text = True
                    await queue.put({"type": "text", "delta": delta})
                if has_text:
                    await queue.put({"type": "text_end"})

        async def consume_tool_calls():
            async for call in stream.tool_calls:
                await queue.put(
                    {
                        "type": "tool_call",
                        "id": call.tool_call_id,
                        "name": call.tool_name,
                        "input": call.input,
                    }
                )
                async for _ in call:  # wait for the tool to finish
                    pass
                if call.error is None:
                    await queue.put(
                        {
                            "type": "tool_result",
                            "id": call.tool_call_id,
                            "output": _as_text(call.output),
                        }
                    )
                # A tool paused by interrupt() surfaces as an error whose message
                # is the Interrupt repr; it's reported as an interrupt event below.
                elif not call.error.startswith("(Interrupt("):
                    await queue.put(
                        {"type": "tool_error", "id": call.tool_call_id, "error": call.error}
                    )

        async def pump():
            # Projections are single-consumer and share one pump, so consume them
            # concurrently and funnel both into one queue.
            try:
                await asyncio.gather(consume_messages(), consume_tool_calls())
            finally:
                queue.put_nowait(None)

        task = asyncio.create_task(pump())
        try:
            while (event := await queue.get()) is not None:
                yield event
            await task  # re-raise anything the consumers raised
        finally:
            task.cancel()

        for interrupt in await stream.interrupts():
            yield {"type": "interrupt", "id": interrupt.id, "value": interrupt.value}
