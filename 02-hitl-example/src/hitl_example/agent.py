import asyncio
import json
import uuid

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import InputAgentState, OutputAgentState
from langchain.mcp import MCPAdapter
from langchain.mcp.elicitation import MCPElicitationInterrupt
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from hitl_example.constants import MCP_SERVER_URL, MODEL

SYSTEM_PROMPT = "You are a helpful assistant. Use the available tools when they help."

type Agent = CompiledStateGraph[AgentState, None, InputAgentState, OutputAgentState]


async def load_mcp_tools() -> list[BaseTool]:
    """Discover the MCP server's tools as LangChain tools.

    The transport (Streamable HTTP) is inferred from the URL. The returned tools
    remain callable after the adapter's context exits.
    """
    async with MCPAdapter(MCP_SERVER_URL) as adapter:
        return await adapter.list_tools()


async def build_agent(model: str | BaseChatModel = MODEL) -> Agent:
    """Create a LangChain agent whose tools come from the MCP server."""
    tools = await load_mcp_tools()
    return create_agent(
        model,
        tools,
        system_prompt=SYSTEM_PROMPT,
        # A checkpointer keeps conversation history per thread_id (and is
        # required later for interrupts / human-in-the-loop).
        checkpointer=InMemorySaver(),
    )


async def chat() -> None:
    agent = await build_agent()
    config: RunnableConfig = {"configurable": {"thread_id": str(uuid.uuid4())}}
    print(f"Connected to {MCP_SERVER_URL}. Type 'exit' to quit.")

    while True:
        try:
            user_input = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue

        await run_turn(agent, config, user_input)


async def run_turn(agent: Agent, config: RunnableConfig, user_input: str) -> None:
    """Stream one agent turn to stdout using the v3 event protocol."""
    stream = await agent.astream_events(
        {"messages": [HumanMessage(user_input, id=str(uuid.uuid4()))]},
        config,
        version="v3",
    )

    async def consume_messages():
        async for message in stream.messages:
            started = False
            async for delta in message.text:
                if not started:
                    print("\nagent> ", end="")
                    started = True
                print(delta, end="", flush=True)
            if started:
                print()

    async def consume_tool_calls():
        async for call in stream.tool_calls:
            print(f"  [tool call] {call.tool_name}({call.input})")
            async for _ in call:  # wait for the tool to finish
                pass
            if call.error is None:
                print(f"  [tool result] {_as_text(call.output)}")
            # A tool paused by interrupt() surfaces as an error whose message is
            # the Interrupt repr; those are reported below once the run stops.
            elif not call.error.startswith("(Interrupt("):
                print(f"  [tool error] {call.error}")

    # Projections are single-consumer and share one pump, so consume them
    # concurrently to see model text and tool calls as they arrive.
    await asyncio.gather(consume_messages(), consume_tool_calls())

    for interrupt in await stream.interrupts():
        print_interrupt(interrupt.value)


def print_interrupt(payload: MCPElicitationInterrupt) -> None:
    """Show what an MCP tool is asking the user for."""
    print(f"  [interrupt] {payload['tool_name']} needs user input (not handled yet)")
    for request in payload["requests"]:
        print(f"    key:     {request['key']}")
        print(f"    message: {request['message']}")
        if request["mode"] == "form":
            schema = json.dumps(request["requested_schema"], indent=2)
            print("    schema:  " + schema.replace("\n", "\n             "))
        else:
            print(f"    url:     {request['url']}")


def _as_text(output) -> str:
    """Flatten a tool's content blocks to plain text."""
    if isinstance(output, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in output
        )
    return str(output)


def main():
    asyncio.run(chat())


if __name__ == "__main__":
    main()
