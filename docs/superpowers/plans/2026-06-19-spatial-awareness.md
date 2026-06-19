# Spatial Awareness for the Editing Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the agent the drawing's spatial frame — bounds, a front/back/left/right orientation (detect → default → user override), and named anchor coordinates in meters — auto-injected into the chat context, so directional requests like "add this to the back of the wall" resolve to real coordinates instead of guesses.

**Architecture:** A new pure module `engine/app/space.py` computes bounds + frame + anchors over a `doc`. The chat endpoint computes the frame each turn and injects a text summary into the agent context (same mechanism as the component list). A `set_entrance` tool lets the user correct orientation; the override is session state in `main.py` (like `_components`), surfaced out of `run_agent` and persisted by the chat handler.

**Tech Stack:** Python 3.12, FastAPI, ezdxf (`ezdxf.bbox.extents`), pytest. Engine-only — no web changes in this phase.

---

## File Structure

```
engine/app/
  space.py          # NEW: drawing_bounds, compute_frame, frame_to_text, orientation detection
  units.py          # (reused) meters_per_unit for unit conversion
  tools.py          # + set_entrance schema + dispatch branch
  agent.py          # run_agent gains frame_text param; surfaces last set_entrance; prompt additions
  main.py           # per-session orientation override; compute+inject frame; persist override
engine/tests/
  test_space.py     # NEW: bounds, anchors, detection, default, override, frame_to_text
  test_tools.py     # + set_entrance dispatch
  test_agent.py     # + frame_text injection; + set_entrance surfaced from run_agent
  test_api.py       # + set_entrance persists into _orientation across turns
```

All work happens on the existing `feat/cad-designer` branch. Engine commands run from `cad-designer/engine` using `.venv/bin/...`.

---

## Conventions to follow (read before starting)

- The fixture `sample_doc` (in `engine/tests/conftest.py`) is a 10×8 m plan (`$INSUNITS=6`, meters): a closed WALLS lwpolyline `(0,0)→(10,0)→(10,8)→(0,8)→(0,0)`, a `CASH COUNTER` TEXT at `(2,2)`, a FIXTURES line `(2,2)→(4,2)`. So its modelspace extents are `min=(0,0)`, `max=(10,8)`.
- `units.meters_per_unit(doc)` returns meters per drawing unit (1.0 for the meters fixture, 0.001 for mm). Convert drawing units → meters by **multiplying** by `meters_per_unit`.
- Change records are dicts `{op, handle, before, after, summary}`; reads return `{"result", "change", "error"}` from `dispatch`.
- Edit/tool functions raise `edits.EntityNotFound` / `edits.ComponentNotFound`; `dispatch` maps those to `error`.

---

# PHASE A — SPACE MODULE

## Task 1: `drawing_bounds`

**Files:**
- Create: `engine/app/space.py`
- Create: `engine/tests/test_space.py`

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_space.py`:
```python
import ezdxf

from app.space import drawing_bounds


def test_bounds_of_sample(sample_doc):
    b = drawing_bounds(sample_doc["doc"])
    assert b is not None
    min_x, min_y, max_x, max_y = b
    assert (round(min_x), round(min_y)) == (0, 0)
    assert (round(max_x), round(max_y)) == (10, 8)


def test_bounds_empty_modelspace():
    doc = ezdxf.new("R2010")
    assert drawing_bounds(doc) is None
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_space.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.space'`

- [ ] **Step 3: Implement `drawing_bounds`**

`engine/app/space.py`:
```python
from ezdxf.bbox import extents
from ezdxf.document import Drawing


def drawing_bounds(doc: Drawing) -> tuple[float, float, float, float] | None:
    """Modelspace extents (min_x, min_y, max_x, max_y) in DRAWING UNITS.
    Returns None when there is no renderable geometry."""
    msp = doc.modelspace()
    try:
        bbox = extents(msp, fast=True)
    except Exception:
        return None
    if not bbox.has_data:
        return None
    return (bbox.extmin.x, bbox.extmin.y, bbox.extmax.x, bbox.extmax.y)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_space.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/space.py engine/tests/test_space.py
git commit -m "feat(engine): drawing_bounds modelspace extents"
```

---

## Task 2: Orientation detection + `compute_frame`

**Files:**
- Modify: `engine/app/space.py`
- Modify: `engine/tests/test_space.py`

`compute_frame` returns bounds in meters, an orientation assignment, and named anchors in meters. Orientation precedence: explicit override → entrance-keyword detection → default (`front=min_y`).

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_space.py`:
```python
import io

from app.space import compute_frame


def test_frame_bounds_and_anchors_meters(sample_doc):
    f = compute_frame(sample_doc["doc"])
    b = f["bounds_m"]
    assert (round(b["width"]), round(b["depth"])) == (10, 8)
    a = f["anchors_m"]
    assert [round(v) for v in a["center"]] == [5, 4]
    # default: front = min_y edge, back = max_y edge
    assert [round(v) for v in a["front_center"]] == [5, 0]
    assert [round(v) for v in a["back_center"]] == [5, 8]
    assert [round(v) for v in a["back_left"]] == [0, 8]


def test_frame_unit_conversion_mm():
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm
    doc.modelspace().add_lwpolyline(
        [(0, 0), (10000, 0), (10000, 8000), (0, 8000), (0, 0)]
    )
    f = compute_frame(doc)
    b = f["bounds_m"]
    assert round(b["width"]) == 10 and round(b["depth"]) == 8  # 10000 mm -> 10 m


def test_frame_default_assumed(sample_doc):
    f = compute_frame(sample_doc["doc"])
    o = f["orientation"]
    assert o["source"] == "assumed"
    assert o["front"] == "min_y" and o["back"] == "max_y" and o["axis"] == "y"


def test_frame_detects_entrance_layer():
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (10, 0), (10, 8), (0, 8), (0, 0)])
    doc.layers.add("ENTRANCE")
    # a marker entity near the max_y edge, on the ENTRANCE layer
    msp.add_line((4, 8), (6, 8), dxfattribs={"layer": "ENTRANCE"})
    f = compute_frame(doc)
    o = f["orientation"]
    assert o["source"] == "detected"
    assert o["front"] == "max_y"  # entrance marker sits at the max_y edge
    # back is the opposite edge; back_center should be at min_y
    assert [round(v) for v in f["anchors_m"]["back_center"]] == [5, 0]


def test_frame_user_override_flips_front():
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 8), (0, 8), (0, 0)])
    f = compute_frame(doc, orientation_override="north")  # entrance at max_y
    o = f["orientation"]
    assert o["source"] == "user"
    assert o["front"] == "max_y" and o["back"] == "min_y"
    assert [round(v) for v in f["anchors_m"]["back_center"]] == [5, 0]


def test_frame_empty_geometry():
    import ezdxf

    f = compute_frame(ezdxf.new("R2010"))
    assert f["bounds_m"] is None
    assert "note" in f
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_space.py -v`
Expected: FAIL with `ImportError: cannot import name 'compute_frame'`

- [ ] **Step 3: Implement `compute_frame` + helpers**

Add to `engine/app/space.py` (keep the existing imports; add the new ones):
```python
from app import units

_ENTRANCE_KEYWORDS = ("door", "entry", "entrance", "glaz", "shutter", "facade")

# Map natural override words to a canonical edge.
_EDGE_ALIASES = {
    "north": "max_y", "top": "max_y", "max_y": "max_y", "back": "max_y",
    "south": "min_y", "bottom": "min_y", "min_y": "min_y", "front": "min_y",
    "east": "max_x", "right": "max_x", "max_x": "max_x",
    "west": "min_x", "left": "min_x", "min_x": "min_x",
}

_OPPOSITE = {"min_y": "max_y", "max_y": "min_y", "min_x": "max_x", "max_x": "min_x"}


def _entity_xy(e):
    """Best-effort representative (x, y) for an entity, in drawing units."""
    try:
        t = e.dxftype()
        if t == "LINE":
            s, end = e.dxf.start, e.dxf.end
            return ((s.x + end.x) / 2, (s.y + end.y) / 2)
        if t in ("TEXT", "MTEXT", "INSERT"):
            p = e.dxf.insert
            return (p.x, p.y)
        if t == "CIRCLE":
            return (e.dxf.center.x, e.dxf.center.y)
        if t == "LWPOLYLINE":
            pts = list(e.get_points())
            if pts:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                return (sum(xs) / len(xs), sum(ys) / len(ys))
    except Exception:
        return None
    return None


def _entrance_centroid(doc):
    """Centroid (drawing units) of entities whose layer or text matches an
    entrance keyword, or None if nothing matches."""
    msp = doc.modelspace()
    pts = []
    for e in msp:
        layer = (e.dxf.layer or "").lower()
        text = ""
        if e.dxftype() == "TEXT":
            text = (e.dxf.text or "").lower()
        elif e.dxftype() == "MTEXT":
            text = (e.text or "").lower()
        hay = layer + " " + text
        if any(k in hay for k in _ENTRANCE_KEYWORDS):
            xy = _entity_xy(e)
            if xy is not None:
                pts.append(xy)
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _nearest_edge(centroid, bounds):
    """Which edge (min_x/max_x/min_y/max_y) the centroid is closest to."""
    cx, cy = centroid
    min_x, min_y, max_x, max_y = bounds
    dists = {
        "min_x": abs(cx - min_x),
        "max_x": abs(cx - max_x),
        "min_y": abs(cy - min_y),
        "max_y": abs(cy - max_y),
    }
    return min(dists, key=dists.get)


def _orientation(doc, bounds, override):
    if override:
        front = _EDGE_ALIASES.get(override.strip().lower())
        if front is not None:
            return front, "user"
    centroid = _entrance_centroid(doc)
    if centroid is not None:
        return _nearest_edge(centroid, bounds), "detected"
    return "min_y", "assumed"  # Lenskart default: entrance at -y


def compute_frame(doc, orientation_override: str | None = None) -> dict:
    """Spatial frame: bounds + orientation + named anchors, in meters."""
    bounds = drawing_bounds(doc)
    if bounds is None:
        return {
            "bounds_m": None,
            "orientation": None,
            "anchors_m": {},
            "note": "drawing has no renderable geometry",
        }

    mpu = units.meters_per_unit(doc)
    min_x, min_y, max_x, max_y = (v * mpu for v in bounds)
    width, depth = max_x - min_x, max_y - min_y

    front, source = _orientation(doc, bounds, orientation_override)
    back = _OPPOSITE[front]
    axis = "y" if front in ("min_y", "max_y") else "x"
    # left/right are the perpendicular edges; "left" = lower coord facing front->back
    if axis == "y":
        left, right = "min_x", "max_x"
    else:
        left, right = "min_y", "max_y"

    cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2

    def edge_point(edge):
        # center point of the named edge
        if edge == "min_x":
            return [min_x, cy]
        if edge == "max_x":
            return [max_x, cy]
        if edge == "min_y":
            return [cx, min_y]
        return [cx, max_y]  # max_y

    def corner(ey, ex):
        x = min_x if ex == "min_x" else max_x
        y = min_y if ey == "min_y" else max_y
        return [x, y]

    anchors = {
        "center": [cx, cy],
        "front_center": edge_point(front),
        "back_center": edge_point(back),
        "left_wall": edge_point(left),
        "right_wall": edge_point(right),
        "front_left": corner(front if axis == "y" else left,
                             left if axis == "y" else front),
        "front_right": corner(front if axis == "y" else right,
                              right if axis == "y" else front),
        "back_left": corner(back if axis == "y" else left,
                            left if axis == "y" else back),
        "back_right": corner(back if axis == "y" else right,
                            right if axis == "y" else back),
    }

    return {
        "bounds_m": {
            "min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y,
            "width": width, "depth": depth,
        },
        "area_sqft": width * depth * 10.7639,
        "orientation": {
            "front": front, "back": back, "left": left, "right": right,
            "axis": axis, "source": source,
        },
        "anchors_m": anchors,
    }
```

Note on `corner`: it takes `(y_edge, x_edge)` where each is one of `min_*/max_*`; the
helper reads only whether each is a min or max on its axis, so passing the front/back edge
(a `*_y` or `*_x` token) and the left/right edge works for both axis orientations.

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_space.py -v`
Expected: PASS (all space tests). If `extents` import differs, confirm with
`.venv/bin/python -c "from ezdxf.bbox import extents; print(extents)"`.

- [ ] **Step 5: Commit**

```bash
git add engine/app/space.py engine/tests/test_space.py
git commit -m "feat(engine): compute_frame with orientation detection and anchors"
```

---

## Task 3: `frame_to_text`

**Files:**
- Modify: `engine/app/space.py`
- Modify: `engine/tests/test_space.py`

A compact, agent-readable summary of the frame.

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_space.py`:
```python
from app.space import frame_to_text


def test_frame_to_text_includes_bounds_and_anchors(sample_doc):
    txt = frame_to_text(compute_frame(sample_doc["doc"]))
    assert "10.0" in txt and "8.0" in txt          # width / depth
    assert "back_center" in txt
    assert "assumed" in txt                          # orientation source surfaced


def test_frame_to_text_empty():
    import ezdxf

    txt = frame_to_text(compute_frame(ezdxf.new("R2010")))
    assert "no renderable geometry" in txt
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_space.py -v`
Expected: FAIL with `ImportError: cannot import name 'frame_to_text'`

- [ ] **Step 3: Implement `frame_to_text`**

Add to `engine/app/space.py`:
```python
def frame_to_text(frame: dict) -> str:
    if frame.get("bounds_m") is None:
        return f"DRAWING FRAME: {frame.get('note', 'no geometry')}."
    b = frame["bounds_m"]
    o = frame["orientation"]
    lines = [
        f"Drawing is {b['width']:.1f} m wide x {b['depth']:.1f} m deep "
        f"(~{frame['area_sqft']:.0f} sqft). Coordinates are meters; "
        f"x in [{b['min_x']:.1f}, {b['max_x']:.1f}], "
        f"y in [{b['min_y']:.1f}, {b['max_y']:.1f}].",
        f"Orientation ({o['source']}): front={o['front']}, back={o['back']}, "
        f"left={o['left']}, right={o['right']} (front->back axis: {o['axis']}).",
        "Anchor points (meters):",
    ]
    for name, xy in frame["anchors_m"].items():
        lines.append(f"  {name}: ({xy[0]:.1f}, {xy[1]:.1f})")
    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_space.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/space.py engine/tests/test_space.py
git commit -m "feat(engine): frame_to_text summary for the agent"
```

---

# PHASE B — TOOL + AGENT WIRING

## Task 4: `set_entrance` tool schema + dispatch

**Files:**
- Modify: `engine/app/tools.py`
- Modify: `engine/tests/test_tools.py`

`set_entrance` records a session orientation override. It does not mutate the doc — dispatch returns the normalized side in `result`.

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_tools.py`:
```python
def test_set_entrance_in_schemas():
    names = {t["name"] for t in TOOL_SCHEMAS}
    assert "set_entrance" in names


def test_dispatch_set_entrance(sample_doc):
    out = dispatch(sample_doc["doc"], "set_entrance", {"side": "north"})
    assert out["error"] is None
    assert out["change"] is None
    assert out["result"] == {"set_entrance": "north"}
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_tools.py -v`
Expected: FAIL (`set_entrance` not in schemas / dispatch returns unknown-tool error)

- [ ] **Step 3: Implement**

In `engine/app/tools.py`, add to `TOOL_SCHEMAS` (before the closing `]`):
```python
    {
        "name": "set_entrance",
        "description": (
            "Record which wall/edge the store ENTRANCE is on, when the user tells "
            "you the orientation (e.g. 'the entrance is on the left'). Use the DRAWING "
            "FRAME's edge names. side is one of: north/top, south/bottom, east/right, "
            "west/left. This re-orients front/back/left/right for the rest of the session."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"side": {"type": "string"}},
            "required": ["side"],
        },
    },
```
In `dispatch`, before the final `Unknown tool` return:
```python
        if name == "set_entrance":
            return {"result": {"set_entrance": str(args["side"])},
                    "change": None, "error": None}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/tools.py engine/tests/test_tools.py
git commit -m "feat(engine): set_entrance tool to record orientation override"
```

---

## Task 5: `run_agent` injects frame text and surfaces `set_entrance`

**Files:**
- Modify: `engine/app/agent.py`
- Modify: `engine/tests/test_agent.py`

`run_agent` gains a `frame_text` param (prepended to the first message) and returns the last `set_entrance` side seen in tool calls as `entrance` (or `None`).

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_agent.py`:
```python
def test_agent_includes_frame_text(sample_doc):
    captured = {}

    class CapturingMessages:
        def create(self, **kwargs):
            captured["messages"] = kwargs["messages"]
            return FakeResponse("end_turn", [FakeBlock(type="text", text="ok")])

    class CapturingClient:
        messages = CapturingMessages()

    run_agent(
        client=CapturingClient(),
        doc=sample_doc["doc"],
        user_message="put it at the back",
        frame_text="DRAWING FRAME: back_center (5.0, 8.0)",
    )
    first = captured["messages"][0]["content"]
    assert "back_center" in first
    assert "put it at the back" in first


def test_agent_surfaces_set_entrance(sample_doc):
    scripted = [
        FakeResponse("tool_use", [
            FakeBlock(type="tool_use", id="t1", name="set_entrance",
                      input={"side": "west"}),
        ]),
        FakeResponse("end_turn", [FakeBlock(type="text", text="Got it.")]),
    ]
    out = run_agent(
        client=FakeClient(scripted),
        doc=sample_doc["doc"],
        user_message="entrance is on the left",
    )
    assert out["entrance"] == "west"
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_agent.py -v`
Expected: FAIL (`frame_text` kwarg unknown / `entrance` key missing)

- [ ] **Step 3: Implement**

In `engine/app/agent.py`, update the signature and the intro/return. Replace the
`run_agent` signature line and the `intro`/`messages` setup:
```python
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
```
Inside the tool-dispatch loop, after `out = dispatch(doc, b.name, b.input)`, capture the
entrance value:
```python
            out = dispatch(doc, b.name, b.input)
            if isinstance(out.get("result"), dict) and "set_entrance" in out["result"]:
                entrance = out["result"]["set_entrance"]
            if out["change"]:
                changes.append(out["change"])
```
Change the final return to include `entrance`:
```python
    return {"reply": reply, "changes": changes, "entrance": entrance}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/agent.py engine/tests/test_agent.py
git commit -m "feat(engine): inject drawing frame and surface set_entrance from agent"
```

---

## Task 6: System-prompt spatial guidance

**Files:**
- Modify: `engine/app/agent.py`

No behavior change to test beyond the existing suite; this updates the `SYSTEM` string.

- [ ] **Step 1: Update the SYSTEM prompt**

In `engine/app/agent.py`, replace the `SYSTEM = (...)` block with:
```python
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
```

- [ ] **Step 2: Run the full engine suite (no regressions)**

Run: `cd engine && .venv/bin/pytest -q`
Expected: PASS (all tests).

- [ ] **Step 3: Commit**

```bash
git add engine/app/agent.py
git commit -m "feat(engine): system prompt teaches the agent to use the drawing frame"
```

---

# PHASE C — ENDPOINT WIRING

## Task 7: Compute + inject frame in chat, persist orientation override

**Files:**
- Modify: `engine/app/main.py`
- Modify: `engine/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_api.py`:
```python
def test_chat_passes_frame_text_to_agent(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    seen = {}

    def fake_run_agent(**kwargs):
        seen["frame_text"] = kwargs.get("frame_text")
        return {"reply": "ok", "changes": [], "entrance": None}

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())
    r = client.post(f"/sessions/{sid}/chat", data={"message": "where is the back?"})
    assert r.status_code == 200
    assert "back_center" in (seen["frame_text"] or "")


def test_chat_persists_entrance_override(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)

    def fake_run_agent(**kwargs):
        return {"reply": "set", "changes": [], "entrance": "north"}

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())
    client.post(f"/sessions/{sid}/chat", data={"message": "entrance is at the top"})
    assert main._orientation.get(sid) == "north"

    # next turn computes the frame with the override -> front becomes max_y
    captured = {}

    def fake_run_agent2(**kwargs):
        captured["frame_text"] = kwargs.get("frame_text")
        return {"reply": "ok", "changes": [], "entrance": None}

    monkeypatch.setattr(main, "run_agent", fake_run_agent2)
    client.post(f"/sessions/{sid}/chat", data={"message": "now where is the front?"})
    assert "front=max_y" in (captured["frame_text"] or "")
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_api.py -v`
Expected: FAIL (`main._orientation` missing / `frame_text` not passed)

- [ ] **Step 3: Implement**

In `engine/app/main.py`:

(a) add the import next to the other `app` imports:
```python
from app import components, space, units
```
(b) add the per-session override registry next to `_components`:
```python
# session_id -> orientation override edge (e.g. "north")
_orientation: dict[str, str] = {}
```
(c) in the `chat` handler, after the attachment-import block and before `store.snapshot(sid)`, build the frame; then pass `frame_text` to `run_agent`; then persist any returned `entrance`. Replace the existing `run_agent(...)` call and the lines around it:
```python
    frame = space.compute_frame(doc, _orientation.get(sid))
    frame_text = space.frame_to_text(frame)

    store.snapshot(sid)
    out = run_agent(
        client=_anthropic_client(),
        doc=doc,
        user_message=message,
        model=MODEL,
        components=_components.get(sid, []),
        frame_text=frame_text,
    )
    if out.get("entrance"):
        _orientation[sid] = out["entrance"]
    if not out["changes"]:
        store.undo(sid)  # discard the no-op snapshot
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Run the full engine suite**

Run: `cd engine && .venv/bin/pytest -q`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add engine/app/main.py engine/tests/test_api.py
git commit -m "feat(engine): inject drawing frame into chat and persist orientation override"
```

---

## Task 8: Manual end-to-end verification

**Files:** none (manual).

- [ ] **Step 1: Restart the engine with the new code**

```bash
lsof -ti :8000 | xargs kill 2>/dev/null
cd engine && .venv/bin/uvicorn app.main:app --reload --port 8000 > /tmp/cad-engine.log 2>&1 &
```

- [ ] **Step 2: Upload a base plan and place at the back**

Upload a real plan (or `/tmp/base_plan.dxf` from earlier), attach a furniture DXF, and say
"place this against the back wall, centered." Confirm in the reply that the AI references
a back anchor (not a guessed center) and that the SVG shows the block near the rear edge.

- [ ] **Step 3: Correct the orientation and re-check**

Say "actually the entrance is on the left." Then "move it to the back." Confirm the AI
calls `set_entrance` and that "back" now resolves to the opposite (right) side.

- [ ] **Step 4: Note results**

Record what worked / any mismatch. No commit (manual step).

---

## Self-Review notes (addressed)

- **Spec coverage:** `space.py` bounds/frame/anchors (T1–T3); orientation detect→default→override (T2); `frame_to_text` (T3); `set_entrance` tool + dispatch (T4); frame injection + entrance surfacing in `run_agent` (T5); system-prompt guidance incl. wall inset + assumed-orientation disclosure (T6); endpoint frame injection + per-session override persistence (T7); manual E2E (T8). Empty-geometry handling covered (T2/T3). Units conversion covered (T2). Web unchanged per spec.
- **No placeholders:** every code step is concrete.
- **Type consistency:** `compute_frame(doc, orientation_override=None)`, `frame_to_text(frame)`, `drawing_bounds(doc)` used consistently across tasks and callers; `run_agent(..., frame_text=...)` and its `{"reply","changes","entrance"}` return match between `agent.py`, tests, and `main.py`; `dispatch` `set_entrance` result shape `{"set_entrance": side}` matches what `run_agent` reads and `main.py` persists into `_orientation`; edge tokens (`min_y`/`max_y`/`min_x`/`max_x`) consistent between `compute_frame`, `frame_to_text`, tests, and the `_EDGE_ALIASES` map.
- **Known risk:** `ezdxf.bbox.extents` signature/`has_data` may vary by version — T1 Step 4 / T2 Step 4 include a quick check. Detection is a heuristic (keyword + nearest-edge); the default + `set_entrance` override are the safety net when it guesses wrong.
```
