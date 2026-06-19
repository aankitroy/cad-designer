from ezdxf.document import Drawing

from app.tools import TOOL_SCHEMAS, dispatch

SYSTEM = (
    "You edit a 2D architectural floor plan (DXF) on the user's behalf. "
    "Always use query_entities or list_layers to locate entities before editing — "
    "never guess a handle. Distances and coordinates you pass are in METERS. "
    "A [DRAWING FRAME] block gives the drawing's bounds, orientation, and named anchor "
    "points (in meters). Use it to resolve directional language — 'back', 'front', "
    "'left/right wall', 'center', a named corner — into real coordinates from the anchors; "
    "never invent coordinates when an anchor applies. When placing a fixture against a "
    "wall, inset it inward from the wall anchor by roughly half the fixture's footprint so "
    "it does not overlap the wall. "
    "If the orientation source is 'assumed' and the request is directional, state the "
    "assumption in your reply (e.g. 'assuming the entrance is at the front/-y edge') and "
    "offer to flip it; if the user tells you where the entrance is, call set_entrance. "
    "If a reference is ambiguous, ask a brief clarifying question instead of guessing. "
    "Organize additions onto layers: pass a `layer` to add_wall/add_text_label to place "
    "entities on a specific layer, and use create_layer to start a new one (e.g. "
    "'Furniture', 'Electrical') so the user's additions stack as separate layers. "
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
    client,
    doc: Drawing,
    user_message: str,
    model: str = "claude-sonnet-4-6",
    components: list[str] | None = None,
    frame_text: str | None = None,
) -> dict:
    parts = []
    if frame_text:
        parts.append(f"[DRAWING FRAME]\n{frame_text}")
    if components:
        parts.append(
            f"[Available components you can place with place_component: "
            f"{', '.join(components)}]"
        )
    parts.append(user_message)
    intro = "\n".join(parts)
    messages = [{"role": "user", "content": intro}]
    changes: list[dict] = []
    entrance: str | None = None
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
            if isinstance(out.get("result"), dict) and "set_entrance" in out["result"]:
                entrance = out["result"]["set_entrance"]
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

    return {"reply": reply, "changes": changes, "entrance": entrance}
