import asyncio

import pytest
from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult

from example_mcp_server.server import mcp


async def call(tool, args, **client_kwargs):
    async with Client(mcp, **client_kwargs) as client:
        return (await client.call_tool(tool, args)).data


def test_add():
    assert asyncio.run(call("add", {"a": 2, "b": 3})) == 5


def test_greet():
    assert asyncio.run(call("greet", {"name": "Eli"})) == "Hello, Eli!"


def make_handler(action):
    async def handler(message, response_type, params, context):
        if action == "accept":
            return {"drink": "latte", "size": "large", "extra_shot": True}
        return ElicitResult(action=action)

    return handler


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("accept", "Ordered a large latte with an extra shot. ☕"),
        ("decline", "No problem, no coffee ordered."),
        ("cancel", "Order cancelled."),
    ],
)
def test_order_coffee(action, expected):
    result = asyncio.run(
        call("order_coffee", {}, elicitation_handler=make_handler(action))
    )
    assert result == expected
