from fastmcp import Context, FastMCP
from mcp_types import (
    ElicitRequest,
    ElicitRequestFormParams,
    InputRequiredResult,
)

from example_mcp_server.constants import HOST, PORT, SERVER_NAME, TRANSPORT

mcp = FastMCP(SERVER_NAME)

COFFEE_FORM = {
    "type": "object",
    "properties": {
        "drink": {"type": "string", "enum": ["latte", "cappuccino", "americano"]},
        "size": {"type": "string", "enum": ["small", "medium", "large"]},
        "extra_shot": {"type": "boolean", "default": False},
    },
    "required": ["drink", "size"],
}


@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@mcp.tool
def greet(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"


@mcp.tool
async def order_coffee(ctx: Context) -> str | InputRequiredResult:
    """Order a coffee. Asks the user which drink and size they want."""
    # Round 1: no answers yet, so ask the client to show the form and call us again.
    responses = ctx.input_responses
    if not responses or "coffee_order" not in responses:
        return InputRequiredResult(
            input_requests={
                "coffee_order": ElicitRequest(
                    params=ElicitRequestFormParams(
                        message="What would you like to order?",
                        requested_schema=COFFEE_FORM,
                    )
                )
            }
        )

    # Round 2: the client retried the call with the user's answer.
    answer = responses["coffee_order"]
    if answer.action == "decline":
        return "No problem, no coffee ordered."
    if answer.action == "cancel":
        return "Order cancelled."

    order = answer.content
    shot = " with an extra shot" if order.get("extra_shot") else ""
    return f"Ordered a {order['size']} {order['drink']}{shot}. ☕"


def main():
    if TRANSPORT == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=TRANSPORT, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
