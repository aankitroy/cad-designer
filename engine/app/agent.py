from ezdxf.document import Drawing

from app.tools import TOOL_SCHEMAS, dispatch

SYSTEM = (
    "You edit a 2D architectural floor plan (DXF) on the user's behalf. "
    "Always use query_entities or list_layers to locate entities before editing — "
    "never guess a handle. Distances and coordinates you pass are in METERS. "
    "If a reference is ambiguous, ask a brief clarifying question instead of guessing. "
    "After making edits, give a one-sentence summary of what changed."
)

MAX_TURNS = 8


def _text_from(content) -> str:
    return " ".join(
        b.text for b in content if getattr(b, "type", None) == "text"
    ).strip()


def _block_to_dict(b) -> dict:
    t = getattr(b, "type", None)
    if t == "text":
        return {"type": "text", "text": b.text}
    if t == "tool_use":
        return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
    return {"type": "text", "text": ""}


def run_agent(
    client, doc: Drawing, user_message: str, model: str = "claude-sonnet-4-6"
) -> dict:
    messages = [{"role": "user", "content": user_message}]
    changes: list[dict] = []
    reply = ""

    for _ in range(MAX_TURNS):
        resp = client.messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        reply = _text_from(resp.content) or reply
        if resp.stop_reason != "tool_use":
            break

        messages.append(
            {"role": "assistant", "content": [_block_to_dict(b) for b in resp.content]}
        )

        tool_results = []
        for b in resp.content:
            if getattr(b, "type", None) != "tool_use":
                continue
            out = dispatch(doc, b.name, b.input)
            if out["change"]:
                changes.append(out["change"])
            payload = out["error"] or out["change"] or out["result"]
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": str(payload),
                    "is_error": bool(out["error"]),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return {"reply": reply, "changes": changes}
