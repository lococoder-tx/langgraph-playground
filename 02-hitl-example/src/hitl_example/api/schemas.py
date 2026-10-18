"""Request and response bodies."""

from typing import Annotated, Any, Literal

from langchain_core.messages import ToolCall
from pydantic import BaseModel, Field


class Thread(BaseModel):
    thread_id: str


class FormRequest(BaseModel):
    key: str
    message: str
    mode: Literal["form"]
    requested_schema: dict[str, Any]


class UrlRequest(BaseModel):
    key: str
    message: str
    mode: Literal["url"]
    url: str


ElicitationRequest = Annotated[FormRequest | UrlRequest, Field(discriminator="mode")]


class ElicitationInterrupt(BaseModel):
    """Mirrors `langchain.mcp.elicitation.MCPElicitationInterrupt`."""

    type: Literal["mcp_elicitation"]
    tool_name: str
    requests: list[ElicitationRequest]


class PendingInterrupt(BaseModel):
    id: str
    value: ElicitationInterrupt


class SendMessage(BaseModel):
    content: str = Field(min_length=1)


class Accept(BaseModel):
    action: Literal["accept"]
    content: dict[str, Any] | None = None


class Decline(BaseModel):
    action: Literal["decline"]


class Cancel(BaseModel):
    action: Literal["cancel"]


Answer = Annotated[Accept | Decline | Cancel, Field(discriminator="action")]


class Resume(BaseModel):
    interrupt_id: str
    # One answer per request `key` in the interrupt, e.g.
    # {"coffee_order": {"action": "accept", "content": {"drink": "latte", ...}}}
    responses: dict[str, Answer]


# class ToolCall(BaseModel):
#     id: str | None
#     name: str
#     args: dict[str, Any]


class Message(BaseModel):
    id: str | None
    type: str  # "human", "ai" or "tool"
    content: str
    tool_calls: list[ToolCall] = []  # ai messages only
    tool_call_id: str | None = None  # tool messages only


class InvokeResult(BaseModel):
    """A whole agent turn, returned at once instead of streamed."""

    # Messages added during this run (not the whole thread history).
    messages: list[Message]
    # The final AI text, or None if the run stopped on an interrupt.
    reply: str | None
    # Answer these via /resume or /resume/invoke before sending a new message.
    interrupts: list[PendingInterrupt]
