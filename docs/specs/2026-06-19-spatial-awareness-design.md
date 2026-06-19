# Spatial Awareness for the Editing Agent (Phase 1)

**Goal:** Let the agent resolve directional placement language — "add this to the
back of the wall", "put it on the left wall", "near the center", "rear-left corner" —
by giving it the drawing's spatial frame: overall bounds, a front/back/left/right
orientation, and named anchor coordinates in meters. Works on any floor plan.

**Status:** Design approved 2026-06-19. Phase 1 of 2 (Phase 2 = the Lenskart placement
playbook: brand sequences, fixture counts, clearance audits — separate spec).

---

## Problem

Today the agent has `list_layers` and `query_entities` (per-entity points) but **no
concept of the drawing's overall extents or orientation**. When asked to place a
component "at the back of the wall" it cannot translate the direction into coordinates,
so it guesses (observed: it placed at a made-up `(3 m, 3 m)` center). The system prompt
([agent.py](../../engine/app/agent.py)) carries no orientation convention and no spatial
vocabulary.

Both Lenskart rule docs agree on a front→back gradient (entrance/facade at the front;
clinics / BOH / toilet at the back). The first guide pins it to coordinates: `−y` =
entrance/front, `+y` = back, x-extremes = side walls. The agent needs that frame.

---

## Scope

**In scope (Phase 1)**
- Compute the drawing's bounds (modelspace extents) in meters.
- Derive a front/back/left/right orientation (detect → default → user override).
- Expose named anchor coordinates (front/back center, left/right wall, center, corners)
  in meters.
- Auto-inject this frame into the agent context every chat turn so directional language
  resolves without a wasted tool call.
- A `set_entrance` tool so the user can correct the orientation ("entrance is on the
  left"); the correction persists for the session.
- System-prompt guidance on using the frame and anchors, including wall-inset by the
  component footprint.

**Out of scope (Phase 2, explicitly deferred)**
- Brand sequences, fixture counts by proto tier, clearance/aisle audits, the `[FP]` /
  `[ANTHRO]` placement playbook reasoning.
- Full automated layout generation from a base shell.
- Unit auto-correction for the "$INSUNITS says feet but geometry is mm" trap — the user
  fixes scale with the existing units selector first.
- Detecting individual wall segments / wall-following placement curves (anchors are
  point/line references, not traced wall paths).

---

## Architecture

Builds on the existing FastAPI + ezdxf engine and Claude tool loop. No new services.

- **`engine/app/space.py`** (new): owns bounds, orientation detection, and frame/anchor
  computation. Pure functions over a `doc` (+ optional override) so they are unit-testable
  without the agent.
- **Session orientation override**: a `dict[session_id, str]` in `main.py` (mirrors the
  existing `_components` registry), holding a user-chosen front side for the session.
- **Context injection**: `main.py` computes the frame each chat turn and passes a text
  block to `run_agent`, which prepends it to the user message (same mechanism as the
  component list).
- **Tools**: `set_entrance` added to `tools.py` schemas + `dispatch`. Because the override
  is session state (not a doc mutation), `dispatch` does not change the doc — it returns
  the normalized side in its `result`. `run_agent` surfaces the last `set_entrance` value
  in its return, and the `main.py` chat handler persists it to the session. See
  "Interfaces" for the exact shapes.

---

## Interfaces

### `engine/app/space.py`

```
drawing_bounds(doc) -> tuple[float, float, float, float] | None
    # (min_x, min_y, max_x, max_y) in DRAWING UNITS via ezdxf.bbox.extents.
    # None when the modelspace has no renderable geometry.

SIDES = {"front", "back", "left", "right"}

compute_frame(doc, orientation_override: str | None = None) -> dict
    # Returns:
    # {
    #   "bounds_m": {"min_x","min_y","max_x","max_y","width","depth"},   # meters
    #   "area_sqft": float,
    #   "orientation": {"front": <edge>, "back": <edge>, "left": <edge>,
    #                   "right": <edge>, "axis": "y"|"x",
    #                   "source": "detected"|"assumed"|"user"},
    #   "anchors_m": {"center", "front_center", "back_center",
    #                 "left_wall", "right_wall",
    #                 "front_left", "front_right", "back_left", "back_right"},
    #   # each anchor is [x_m, y_m]
    # }
    # Returns a frame with bounds_m=None and a note when geometry is empty.
```

**Orientation detection heuristic** (in `compute_frame`):
1. If `orientation_override` is given (a side keyword), use it → `source="user"`.
2. Else scan layer names and TEXT/MTEXT content for entrance keywords
   (`door`, `entry`, `entrance`, `glaz`, `shutter`, `facade`). If matches exist, take the
   centroid of matching entities; the bounds edge nearest that centroid is `front`, and
   the axis (x or y) is the one along which that edge lies → `source="detected"`.
3. Else default: front = `min_y` edge, back = `max_y` edge, axis = `y`
   (Lenskart convention) → `source="assumed"`.

`left`/`right` are the two edges perpendicular to the front→back axis, assigned so that
"left" is the lower coordinate when facing from front to back.

The override keyword maps a *physical edge* to "front": `"bottom"|"south"|"min_y"`,
`"top"|"north"|"max_y"`, `"left"|"west"|"min_x"`, `"right"|"east"|"max_x"`, and the four
plain side words; normalize to one of those edges.

### `engine/app/tools.py`

Add one schema:
```
set_entrance(side: str)
    # side names the edge/wall where the store entrance is, as a natural word:
    #   "north"|"top"|"max_y", "south"|"bottom"|"min_y",
    #   "east"|"right"|"max_x", "west"|"left"|"min_x".
    # space.compute_frame normalizes these to a single canonical edge.
    # Records the session orientation override; does not mutate the doc.
```
`dispatch` recognizes `set_entrance` and returns
`{"result": {"set_entrance": <normalized_side>}, "change": None, "error": None}` (it does
not mutate the doc). The chat handler in `main.py` reads that result and stores the
override for the session, then the next frame computation reflects it.

### `engine/app/agent.py`

```
run_agent(client, doc, user_message, model=..., components=None, frame_text: str | None = None)
```
When `frame_text` is provided, prepend it (and the existing component list, if any) to the
first user message:
```
[DRAWING FRAME]
<frame_text>
[Available components ...]
<user_message>
```

### `engine/app/main.py`

- `_orientation: dict[str, str] = {}` — session → override edge.
- In the chat handler, after any attachment import and before `run_agent`:
  - `frame = space.compute_frame(doc, _orientation.get(sid))`
  - render `frame` to a compact text block (`space.frame_to_text(frame)`).
  - pass `frame_text=...` to `run_agent`.
- After the agent loop, if any tool call returned a `set_entrance` result, persist it to
  `_orientation[sid]`. (Implementation: `dispatch` already ran inside `run_agent`; expose
  the captured `set_entrance` value through `run_agent`'s return, e.g.
  `{"reply","changes","entrance"}`, and `main.py` stores it.)

---

## Data flow

1. `POST /sessions/{id}/chat` (existing multipart endpoint).
2. Import attachment if present (unchanged).
3. `compute_frame(doc, override)` → `frame_to_text` → inject into agent context.
4. Agent reads the frame, resolves the directional reference to an anchor coordinate,
   insets by the component footprint where placing against a wall, and calls
   `place_component` / `add_*` with meter coordinates.
5. If the user corrected the orientation, the agent calls `set_entrance`; the handler
   stores it so subsequent turns use the corrected frame.
6. Re-render + return (unchanged).

---

## System-prompt additions

Append to `SYSTEM` in `agent.py`:
- A DRAWING FRAME is provided with the drawing's bounds, orientation, and named anchor
  coordinates (in meters). Use it to resolve directional language — "back", "front",
  "left/right wall", "center", "<corner>" — to real coordinates. Do not guess coordinates.
- When placing a fixture against a wall, inset it inward from the wall anchor by roughly
  half the component's footprint so it does not overlap the wall.
- If `orientation.source` is `assumed` and the request is directional, state the
  assumption in your reply ("assuming the entrance is at the −y/front edge") and offer to
  flip it; if the user gives a correction, call `set_entrance`.

---

## Error handling

- Empty modelspace → frame with `bounds_m=None`; `frame_to_text` says geometry is empty;
  the agent asks the user for a reference or proceeds without anchors (no crash).
- `bbox.extents` raising (degenerate geometry) → treated as empty bounds, same path.
- `set_entrance` with an unrecognized side → tool returns an error result; agent re-asks.
- Frame computation never blocks an edit: a failure logs and the agent simply lacks
  anchors for that turn.

---

## Testing (TDD)

**Engine (pytest)**
- `drawing_bounds` returns correct extents for `sample_doc`; `None` for empty modelspace.
- `compute_frame` anchors: `center`, `back_center`, `left_wall`, corners computed correctly
  in meters for a meters fixture and a mm fixture (unit conversion correct).
- Detection: a doc with an "ENTRANCE" layer (or text) at the min-y edge → `front` = min-y,
  `source="detected"`.
- Default: no keywords → `front=min_y`, `source="assumed"`.
- Override: `compute_frame(doc, "north")` flips `back` to the min-y edge; `source="user"`.
- `frame_to_text` includes bounds, orientation source, and anchor coordinates.
- Tool dispatch: `set_entrance` returns the normalized side and no change; unknown side
  → error.
- `run_agent` prepends the frame text to the first message (capturing-client test).
- Chat endpoint: a `set_entrance` tool call persists the override into `_orientation`
  (agent mocked); subsequent frame reflects it.

**Web (Vitest)**
- No web changes in Phase 1 (the frame is engine-internal; the chat UI is unchanged).

---

## Stack / files

- Engine: `space.py` (new), `tools.py` (+`set_entrance`), `agent.py` (`frame_text` param +
  prompt), `main.py` (frame injection + orientation store). Tests alongside.
- Model unchanged (Claude Sonnet 4.6 tool loop).
