"""Streamlit demo UI for the HITL API. Run: `uv run streamlit run src/hitl_example/ui.py`."""

import json

import httpx
import streamlit as st

from hitl_example.constants import API_HOST, API_PORT

API = f"http://{API_HOST}:{API_PORT}/threads"

st.set_page_config(page_title="HITL demo", page_icon="💬")
ss = st.session_state
ss.setdefault("thread_id", None)
# Turns: {"role": "user", "text": ...} or {"role": "assistant", "items": [...]}
ss.setdefault("history", [])
ss.setdefault("interrupt", None)

with st.sidebar:
    if st.button("New chat", width="stretch"):
        ss.clear()
        st.rerun()
    st.caption(f"API: {API}")
    st.caption(f"Thread: {ss.thread_id or '-'}")


def thread_id() -> str:
    if ss.thread_id is None:
        ss.thread_id = httpx.post(API).raise_for_status().json()["thread_id"]
    return ss.thread_id


def show_tool(item: dict):
    """Draw a tool call; returns the status box so a live run can update it."""
    box = st.status(f"`{item['name']}`", state=item["state"], expanded=False)
    box.json(item["input"])
    if "output" in item:
        box.code(item["output"], language=None)
    return box


def finish_tool(box, item: dict, state: str, output: str):
    item["state"], item["output"] = state, output
    box.code(output, language=None)
    box.update(state=state)


def show_items(items: list[dict]):
    for item in items:
        if item["kind"] == "text":
            st.markdown(item["text"])
        elif item["kind"] == "tool":
            show_tool(item)
        else:
            st.error(item["text"])


def stream(path: str, body: dict):
    """POST to a streaming endpoint and draw its NDJSON events as they arrive."""
    url = f"{API}/{thread_id()}/{path}"
    with httpx.stream("POST", url, json=body, timeout=None) as r:
        if r.is_error:
            r.read()
            st.error(f"{r.status_code}: {r.text}")
            return

        # A resumed tool reports its result without a fresh tool_call event.
        paused_tool = ss.interrupt["value"]["tool_name"] if ss.interrupt else "tool"
        ss.interrupt = None
        items: list[dict] = []
        ss.history.append({"role": "assistant", "items": items})
        tools = {}  # tool call id -> (status box, item)
        text, placeholder = "", None

        def tool(call_id: str):
            if call_id not in tools:
                item = {"kind": "tool", "name": paused_tool, "input": {}, "state": "running"}
                items.append(item)
                tools[call_id] = (show_tool(item), item)
            return tools[call_id]

        with st.chat_message("assistant"):
            for line in r.iter_lines():
                if not line:
                    continue
                ev = json.loads(line)
                match ev["type"]:
                    case "text":
                        placeholder = placeholder or st.empty()
                        text += ev["delta"]
                        placeholder.markdown(text)
                    case "text_end":
                        items.append({"kind": "text", "text": text})
                        text, placeholder = "", None
                    case "tool_call":
                        item = {
                            "kind": "tool",
                            "name": ev["name"],
                            "input": ev["input"],
                            "state": "running",
                        }
                        items.append(item)
                        tools[ev["id"]] = (show_tool(item), item)
                    case "tool_result":
                        finish_tool(*tool(ev["id"]), "complete", ev["output"])
                    case "tool_error":
                        finish_tool(*tool(ev["id"]), "error", ev["error"])
                    case "interrupt":
                        ss.interrupt = ev
                    case "error":
                        items.append({"kind": "error", "text": ev["message"]})
                        st.error(ev["message"])
        if text:
            items.append({"kind": "text", "text": text})

    # Tools still "running" were paused by the interrupt.
    for _, item in tools.values():
        if item["state"] == "running":
            item["state"] = "complete"
            item["output"] = "Waiting for your input…"
    st.rerun()


def form_field(name: str, prop: dict, required: bool):
    label = prop.get("title", name) + ("" if required else " (optional)")
    default = prop.get("default")
    hint = prop.get("description")
    if "enum" in prop:
        options = prop["enum"]
        index = options.index(default) if default in options else (0 if required else None)
        return st.selectbox(label, options, index=index, help=hint)
    match prop.get("type"):
        case "boolean":
            return st.checkbox(label, value=bool(default), help=hint)
        case "integer":
            return st.number_input(label, value=default, step=1, help=hint)
        case "number":
            return st.number_input(label, value=default, help=hint)
        case _:
            return st.text_input(label, value=default or "", help=hint)


def interrupt_form(interrupt: dict):
    value = interrupt["value"]
    with st.chat_message("assistant"), st.form("interrupt_form"):
        st.markdown(f"**`{value['tool_name']}` needs your input**")
        contents = {}
        for req in value["requests"]:
            st.markdown(req["message"])
            if req["mode"] == "url":
                st.link_button("Open link", req["url"])
                continue
            schema = req["requested_schema"]
            required = set(schema.get("required", []))
            fields = {
                name: form_field(name, prop, name in required)
                for name, prop in schema.get("properties", {}).items()
            }
            # Leave out unanswered optional fields rather than sending blanks.
            contents[req["key"]] = {k: v for k, v in fields.items() if v not in (None, "")}

        cols = st.columns(3)
        accept = cols[0].form_submit_button("Accept", type="primary", width="stretch")
        decline = cols[1].form_submit_button("Decline", width="stretch")
        cancel = cols[2].form_submit_button("Cancel", width="stretch")

    action = "accept" if accept else "decline" if decline else "cancel" if cancel else None
    if action is None:
        return
    responses = {}
    for req in value["requests"]:
        answer = {"action": action}
        if action == "accept" and req["key"] in contents:
            answer["content"] = contents[req["key"]]
        responses[req["key"]] = answer
    stream("resume", {"interrupt_id": interrupt["id"], "responses": responses})


for turn in ss.history:
    with st.chat_message(turn["role"]):
        if turn["role"] == "user":
            st.markdown(turn["text"])
        else:
            show_items(turn["items"])

if ss.interrupt:
    interrupt_form(ss.interrupt)

if prompt := st.chat_input("Message", disabled=ss.interrupt is not None):
    ss.history.append({"role": "user", "text": prompt})
    st.chat_message("user").markdown(prompt)
    stream("messages", {"content": prompt})
