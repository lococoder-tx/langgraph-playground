"""HTTP API that lets a browser frontend chat with the agent and answer elicitations.

Agent runs stream back as NDJSON: a chunked HTTP response with one JSON event per
line (see `hitl_example.events`). Read it with `fetch()` + `response.body.getReader()`.
`/messages/invoke` and `/resume/invoke` do the same without streaming, returning the
whole turn as one JSON `InvokeResult`.

Flow:
1. `POST /threads` -> `{"thread_id": ...}`
2. `POST /threads/{id}/messages` streams the turn. If a tool needs input, the last
   event is `{"type": "interrupt", "id": ..., "value": {...requested_schema...}}`
   and the response ends; the paused run is saved by the checkpointer.
3. Render a form from the schema, then `POST /threads/{id}/resume` with the answers
   to stream the rest of the run (which may interrupt again).
"""

from hitl_example.api.app import create_app, main

__all__ = ["create_app", "main"]
