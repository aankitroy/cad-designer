# In-Chat Component Placement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user attach a DXF to a chat message; the engine imports it as a named block (scaled to the base drawing's units), the AI places it via a `place_component` tool from natural language, and placed components are editable via chat (move/rotate/delete).

**Architecture:** Extends the existing FastAPI + ezdxf engine and Claude tool loop. Attached DXF geometry is imported into the session doc as a block via `ezdxf.addons.importer.Importer`, with the component→base unit scale baked in at import so the block lives in base units. Placement is a normal `INSERT` (so existing move/delete tools work; a new `rotate_entity` is added). The chat endpoint becomes multipart; the web chat input gets a file-attach button.

**Tech Stack:** Python, FastAPI, ezdxf (Importer, Matrix44), pytest; Next.js, TypeScript, Vitest.

---

## File Structure

```
engine/app/
  components.py     # NEW: import an attached DXF as a block (unit-scaled)
  units.py          # + meters_per_unit(doc)
  edits.py          # + place_component, rotate_entity
  query.py          # INSERT results gain a "block" field
  tools.py          # + place_component, rotate_entity schemas + dispatch
  agent.py          # run_agent gains optional component-context note
  main.py           # chat endpoint -> multipart (optional file) + import
engine/tests/
  conftest.py       # + component_bytes fixture
  test_units.py test_components.py test_edits.py test_query.py test_tools.py
  test_agent.py test_api.py
web/
  lib/api.ts                 # sendChat(sid, message, file?) -> multipart when file
  components/ChatPanel.tsx   # paperclip attach button + filename chip
  app/page.tsx               # thread attached file through handleSend
  __tests__/api.test.ts ChatPanel.test.tsx
```

---

# PHASE A — ENGINE

## Task 1: `meters_per_unit` helper

**Files:** Modify `engine/app/units.py`, `engine/tests/test_units.py`

- [ ] **Step 1: Write the failing test**

Append to `engine/tests/test_units.py`:
```python
from app.units import meters_per_unit


def test_meters_per_unit_mm():
    import ezdxf
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm
    assert meters_per_unit(doc) == 0.001


def test_meters_per_unit_default_meters(sample_doc):
    assert meters_per_unit(sample_doc["doc"]) == 1.0  # fixture is meters
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_units.py -v`
Expected: FAIL `ImportError: cannot import name 'meters_per_unit'`

- [ ] **Step 3: Implement**

In `engine/app/units.py`, add the function and refactor the existing converter to use it:
```python
def meters_per_unit(doc: Drawing) -> float:
    code = int(doc.header.get("$INSUNITS", 0))
    return _METERS_PER_UNIT.get(code, 1.0)


def meters_to_drawing_units(doc: Drawing, meters: float) -> float:
    return meters / meters_per_unit(doc)
```
(Delete the old body of `meters_to_drawing_units`; keep the new one above.)

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_units.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/units.py engine/tests/test_units.py
git commit -m "feat(engine): add meters_per_unit helper"
```

---

## Task 2: Import an attached DXF as a block

**Files:** Create `engine/app/components.py`, `engine/tests/test_components.py`; Modify `engine/tests/conftest.py`

- [ ] **Step 1: Add a component fixture**

Append to `engine/tests/conftest.py`:
```python
@pytest.fixture
def component_bytes():
    """A small 'chair' component DXF in millimeters (500x500 box + a back line)."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (500, 0), (500, 500), (0, 500), (0, 0)])
    msp.add_line((100, 500), (400, 500))
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")
```

- [ ] **Step 2: Write the failing tests**

`engine/tests/test_components.py`:
```python
import io

import ezdxf
import pytest

from app.components import import_as_block


def _base_doc(insunits=6):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = insunits
    return doc


def test_import_creates_block(component_bytes):
    doc = _base_doc()
    name = import_as_block(doc, component_bytes, "chair.dxf")
    assert name == "chair"
    assert name in doc.blocks
    assert len(list(doc.blocks.get(name))) >= 2
    # modelspace unchanged until something is placed
    assert len(list(doc.modelspace())) == 0


def test_import_bakes_unit_scale(component_bytes):
    # component is mm (500 units = 0.5 m); base is meters -> block should be ~0.5 wide
    doc = _base_doc(insunits=6)
    name = import_as_block(doc, component_bytes, "chair.dxf")
    from ezdxf.bbox import extents
    bb = extents(doc.blocks.get(name))
    assert bb.size.x == pytest.approx(0.5, abs=1e-6)


def test_import_dedupes_name(component_bytes):
    doc = _base_doc()
    n1 = import_as_block(doc, component_bytes, "chair.dxf")
    n2 = import_as_block(doc, component_bytes, "chair.dxf")
    assert n1 == "chair" and n2 == "chair_2"


def test_import_rejects_garbage():
    doc = _base_doc()
    with pytest.raises(ValueError):
        import_as_block(doc, b"not a dxf", "x.dxf")


def test_import_rejects_empty_geometry():
    empty = ezdxf.new("R2010")
    buf = io.StringIO()
    empty.write(buf)
    doc = _base_doc()
    with pytest.raises(ValueError):
        import_as_block(doc, buf.getvalue().encode(), "empty.dxf")
```

- [ ] **Step 3: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_components.py -v`
Expected: FAIL `ModuleNotFoundError: app.components`

- [ ] **Step 4: Implement**

`engine/app/components.py`:
```python
import io
import re

import ezdxf
from ezdxf.addons import importer
from ezdxf.document import Drawing
from ezdxf.math import Matrix44

from app import units


def _unique_block_name(doc: Drawing, filename: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", filename.rsplit(".", 1)[0]) or "component"
    name = base
    i = 2
    while name in doc.blocks:
        name = f"{base}_{i}"
        i += 1
    return name


def import_as_block(doc: Drawing, dxf_bytes: bytes, filename: str) -> str:
    """Import an attached DXF's modelspace into a new block in `doc`, scaled so the
    block is expressed in `doc`'s drawing units. Returns the new block name."""
    try:
        src = ezdxf.read(io.StringIO(dxf_bytes.decode("utf-8", errors="replace")))
    except Exception as exc:  # ezdxf.DXFStructureError and friends
        raise ValueError(f"Not a valid DXF file: {exc}") from exc

    if len(list(src.modelspace())) == 0:
        raise ValueError("Attached DXF has no drawable geometry")

    name = _unique_block_name(doc, filename)
    block = doc.blocks.new(name=name)
    imp = importer.Importer(src, doc)
    imp.import_modelspace(target_layout=block)
    imp.finalize()

    scale = units.meters_per_unit(src) / units.meters_per_unit(doc)
    if abs(scale - 1.0) > 1e-9:
        m = Matrix44.scale(scale, scale, scale)
        for entity in block:
            try:
                entity.transform(m)
            except Exception:  # noqa: BLE001 - skip entities that can't transform
                pass
    return name
```

- [ ] **Step 5: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_components.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add engine/app/components.py engine/tests/test_components.py engine/tests/conftest.py
git commit -m "feat(engine): import attached DXF as a unit-scaled block"
```

---

## Task 3: `place_component` and `rotate_entity` edit ops

**Files:** Modify `engine/app/edits.py`, `engine/tests/test_edits.py`

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_edits.py`:
```python
import math


def test_place_component(sample_doc):
    from app.components import import_as_block
    doc = sample_doc["doc"]
    # build a component bytes inline
    import io, ezdxf
    cdoc = ezdxf.new("R2010"); cdoc.header["$INSUNITS"] = 6
    cdoc.modelspace().add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    buf = io.StringIO(); cdoc.write(buf)
    name = import_as_block(doc, buf.getvalue().encode(), "table.dxf")

    change = edits.place_component(doc, name, x=5, y=5, rotation_deg=90, scale=2.0)
    assert change["op"] == "place_component"
    ins = doc.entitydb[change["handle"]]
    assert ins.dxftype() == "INSERT"
    assert ins.dxf.name == name
    assert ins.dxf.insert.x == 5 and ins.dxf.insert.y == 5
    assert ins.dxf.rotation == 90
    assert ins.dxf.xscale == 2.0


def test_place_component_unknown_block(sample_doc):
    with pytest.raises(edits.ComponentNotFound):
        edits.place_component(sample_doc["doc"], "nope", x=0, y=0)


def test_rotate_insert(sample_doc):
    from app.components import import_as_block
    import io, ezdxf
    doc = sample_doc["doc"]
    cdoc = ezdxf.new("R2010"); cdoc.header["$INSUNITS"] = 6
    cdoc.modelspace().add_line((0, 0), (1, 0))
    buf = io.StringIO(); cdoc.write(buf)
    name = import_as_block(doc, buf.getvalue().encode(), "c.dxf")
    ch = edits.place_component(doc, name, x=0, y=0)
    rot = edits.rotate_entity(doc, ch["handle"], 45)
    assert rot["op"] == "rotate_entity"
    assert doc.entitydb[ch["handle"]].dxf.rotation == 45


def test_rotate_line_about_its_point(sample_doc):
    doc = sample_doc["doc"]
    change = edits.rotate_entity(doc, sample_doc["line_handle"], 90)
    assert change["op"] == "rotate_entity"


def test_rotate_missing_handle(sample_doc):
    with pytest.raises(edits.EntityNotFound):
        edits.rotate_entity(sample_doc["doc"], "DEADBEEF", 30)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_edits.py -v`
Expected: FAIL (`place_component`/`rotate_entity`/`ComponentNotFound` missing)

- [ ] **Step 3: Implement**

In `engine/app/edits.py`, add (top, near `EntityNotFound`):
```python
class ComponentNotFound(Exception):
    pass
```
Add these functions:
```python
def place_component(doc: Drawing, name: str, x: float, y: float,
                    rotation_deg: float = 0.0, scale: float = 1.0) -> dict:
    if name not in doc.blocks:
        raise ComponentNotFound(f"No component named {name!r}")
    ins = doc.modelspace().add_blockref(
        name, (x, y),
        dxfattribs={"xscale": scale, "yscale": scale, "rotation": rotation_deg},
    )
    return {
        "op": "place_component",
        "handle": ins.dxf.handle,
        "before": None,
        "after": name,
        "summary": f"Placed '{name}' at ({x}, {y})",
    }


def rotate_entity(doc: Drawing, handle: str, angle_deg: float) -> dict:
    import math as _math
    from ezdxf.math import Matrix44

    e = _get(doc, handle)
    if e.dxftype() == "INSERT":
        before = e.dxf.rotation
        e.dxf.rotation = (e.dxf.rotation + angle_deg) % 360
        after = e.dxf.rotation
    else:
        pt = _summarize_point(e) or [0.0, 0.0]
        m = (
            Matrix44.translate(-pt[0], -pt[1], 0)
            @ Matrix44.z_rotate(_math.radians(angle_deg))
            @ Matrix44.translate(pt[0], pt[1], 0)
        )
        e.transform(m)
        before, after = 0.0, angle_deg
    return {
        "op": "rotate_entity",
        "handle": handle,
        "before": before,
        "after": after,
        "summary": f"Rotated {e.dxftype()} by {angle_deg}°",
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_edits.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/edits.py engine/tests/test_edits.py
git commit -m "feat(engine): place_component and rotate_entity edit ops"
```

---

## Task 4: `query_entities` reports block name for INSERTs

**Files:** Modify `engine/app/query.py`, `engine/tests/test_query.py`

- [ ] **Step 1: Write the failing test**

Append to `engine/tests/test_query.py`:
```python
def test_query_reports_block_name_for_inserts():
    import io, ezdxf
    from app.components import import_as_block
    doc = ezdxf.new("R2010"); doc.header["$INSUNITS"] = 6
    cdoc = ezdxf.new("R2010"); cdoc.header["$INSUNITS"] = 6
    cdoc.modelspace().add_line((0, 0), (1, 0))
    buf = io.StringIO(); cdoc.write(buf)
    name = import_as_block(doc, buf.getvalue().encode(), "sofa.dxf")
    doc.modelspace().add_blockref(name, (0, 0))

    results = query_entities(doc, type="INSERT")
    assert any(r.get("block") == name for r in results)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_query.py::test_query_reports_block_name_for_inserts -v`
Expected: FAIL (KeyError / None)

- [ ] **Step 3: Implement**

In `engine/app/query.py`, inside `query_entities`, where the result dict is built, add a `block` field:
```python
        out.append(
            {
                "handle": e.dxf.handle,
                "type": e.dxftype(),
                "layer": e_layer,
                "text": text,
                "point": pt,
                "block": e.dxf.name if e.dxftype() == "INSERT" else None,
            }
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_query.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/query.py engine/tests/test_query.py
git commit -m "feat(engine): query_entities reports block name for INSERTs"
```

---

## Task 5: Tools + dispatch + agent component context

**Files:** Modify `engine/app/tools.py`, `engine/app/agent.py`, `engine/tests/test_tools.py`, `engine/tests/test_agent.py`

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_tools.py`:
```python
def test_place_and_rotate_in_schemas():
    names = {t["name"] for t in TOOL_SCHEMAS}
    assert {"place_component", "rotate_entity"} <= names


def test_dispatch_place_component_converts_meters(sample_doc):
    import io, ezdxf
    from app.components import import_as_block
    doc = sample_doc["doc"]  # meters
    cdoc = ezdxf.new("R2010"); cdoc.header["$INSUNITS"] = 6
    cdoc.modelspace().add_line((0, 0), (1, 0))
    buf = io.StringIO(); cdoc.write(buf)
    name = import_as_block(doc, buf.getvalue().encode(), "c.dxf")

    out = dispatch(doc, "place_component",
                   {"name": name, "x_m": 3.0, "y_m": 0.0, "rotation_deg": 0})
    assert out["change"]["op"] == "place_component"
    ins = doc.entitydb[out["change"]["handle"]]
    assert abs(ins.dxf.insert.x - 3.0) < 1e-6  # meters base -> 3 units


def test_dispatch_rotate(sample_doc):
    out = dispatch(sample_doc["doc"], "rotate_entity",
                   {"handle": sample_doc["line_handle"], "angle_deg": 30})
    assert out["change"]["op"] == "rotate_entity"
```

Append to `engine/tests/test_agent.py`:
```python
def test_agent_includes_component_context(sample_doc):
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
        user_message="place it by the door",
        components=["chair"],
    )
    first = captured["messages"][0]["content"]
    assert "chair" in first
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_tools.py tests/test_agent.py -v`
Expected: FAIL (schemas/dispatch/`components` kwarg missing)

- [ ] **Step 3: Implement tools**

In `engine/app/tools.py`, add to `TOOL_SCHEMAS`:
```python
    {
        "name": "place_component",
        "description": (
            "Place a previously-attached component (a block, by name) into the drawing "
            "at a point in meters. Use list_layers/query_entities to locate a reference "
            "point first (e.g. near the door). rotation_deg rotates the placement; scale "
            "multiplies its size (1.0 = real size)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "component/block name"},
                "x_m": {"type": "number"},
                "y_m": {"type": "number"},
                "rotation_deg": {"type": "number"},
                "scale": {"type": "number"},
            },
            "required": ["name", "x_m", "y_m"],
        },
    },
    {
        "name": "rotate_entity",
        "description": "Rotate an entity (e.g. a placed component) by angle_deg degrees.",
        "input_schema": {
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "angle_deg": {"type": "number"},
            },
            "required": ["handle", "angle_deg"],
        },
    },
```
In `dispatch`, before the final `Unknown tool` return, add:
```python
        if name == "place_component":
            c = edits.place_component(
                doc, args["name"], m(args["x_m"]), m(args["y_m"]),
                rotation_deg=float(args.get("rotation_deg", 0.0)),
                scale=float(args.get("scale", 1.0)),
            )
            return {"result": None, "change": c, "error": None}
        if name == "rotate_entity":
            c = edits.rotate_entity(doc, args["handle"], float(args["angle_deg"]))
            return {"result": None, "change": c, "error": None}
```
Add to the `except` clauses in `dispatch` (alongside `edits.EntityNotFound`):
```python
    except edits.ComponentNotFound as e:
        return {"result": None, "change": None, "error": str(e)}
```

- [ ] **Step 4: Implement agent context**

In `engine/app/agent.py`, change `run_agent` signature and prepend context:
```python
def run_agent(client, doc: Drawing, user_message: str,
              model: str = "claude-sonnet-4-6", components: list[str] | None = None) -> dict:
    intro = user_message
    if components:
        intro = (
            f"[Available components you can place: {', '.join(components)}]\n{user_message}"
        )
    messages = [{"role": "user", "content": intro}]
    # ... rest unchanged (changes/reply loop)
```
(Only the first `messages` construction changes; the loop body stays the same.)

- [ ] **Step 5: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_tools.py tests/test_agent.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add engine/app/tools.py engine/app/agent.py engine/tests/test_tools.py engine/tests/test_agent.py
git commit -m "feat(engine): place_component/rotate_entity tools + agent component context"
```

---

## Task 6: Multipart chat endpoint with attachment

**Files:** Modify `engine/app/main.py`, `engine/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_api.py`:
```python
def test_chat_with_attachment_imports_and_exposes_component(sample_bytes, component_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    seen = {}

    def fake_run_agent(**kwargs):
        seen["components"] = kwargs.get("components")
        from app import edits
        name = kwargs["components"][0]
        c = edits.place_component(kwargs["doc"], name, 0, 0)
        return {"reply": "placed", "changes": [c]}

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())

    r = client.post(
        f"/sessions/{sid}/chat",
        data={"message": "place the chair by the door"},
        files={"file": ("chair.dxf", io.BytesIO(component_bytes), "application/dxf")},
    )
    assert r.status_code == 200
    assert seen["components"] == ["chair"]
    assert r.json()["changes"][0]["op"] == "place_component"


def test_chat_without_attachment_still_works(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    monkeypatch.setattr(main, "run_agent",
                        lambda **k: {"reply": "ok", "changes": []})
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())
    r = client.post(f"/sessions/{sid}/chat", data={"message": "hi"})
    assert r.status_code == 200


def test_chat_rejects_bad_attachment(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())
    r = client.post(
        f"/sessions/{sid}/chat",
        data={"message": "place this"},
        files={"file": ("x.dxf", io.BytesIO(b"junk"), "application/dxf")},
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_api.py -v`
Expected: FAIL (chat is JSON-only; no file handling)

- [ ] **Step 3: Implement**

In `engine/app/main.py`: add import `from app import components` (next to other `app` imports), track per-session component names, and replace the `chat` handler. Add a module-level registry and change the handler to Form/File:
```python
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

# ... existing code ...

# session_id -> list of imported component (block) names
_components: dict[str, list[str]] = {}


@app.post("/sessions/{sid}/chat")
async def chat(
    sid: str,
    message: str = Form(...),
    file: UploadFile | None = File(default=None),
) -> dict:
    doc = store.get(sid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown session")

    if file is not None:
        data = await file.read()
        try:
            name = components.import_as_block(doc, data, file.filename or "component.dxf")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        _components.setdefault(sid, []).append(name)

    store.snapshot(sid)
    out = run_agent(
        client=_anthropic_client(), doc=doc, user_message=message, model=MODEL,
        components=_components.get(sid, []),
    )
    if not out["changes"]:
        store.undo(sid)
    current = store.get(sid)
    return {
        "reply": out["reply"],
        "changes": out["changes"],
        "svg": render_svg(current),
        "layers": list_layers(current),
    }
```
Remove the old `ChatRequest`-based `chat` function and the now-unused `ChatRequest` model if nothing else uses it. (Keep `UnitsRequest`.)

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/ -v`
Expected: PASS (all engine tests). If an old test posted `json={"message": ...}` to chat, update it to `data={"message": ...}`.

- [ ] **Step 5: Commit**

```bash
git add engine/app/main.py engine/tests/test_api.py
git commit -m "feat(engine): multipart chat endpoint imports attached component"
```

---

# PHASE B — WEB

## Task 7: `sendChat` supports a file attachment

**Files:** Modify `web/lib/api.ts`, `web/__tests__/api.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `web/__tests__/api.test.ts`:
```ts
it("sendChat sends multipart when a file is attached", async () => {
  const body = { reply: "ok", changes: [], svg: "<svg/>", layers: [] };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const file = new File(["x"], "chair.dxf");
  await sendChat("s1", "place it", file);
  const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(call[1].body).toBeInstanceOf(FormData);
});

it("sendChat sends form fields without a file too", async () => {
  const body = { reply: "ok", changes: [], svg: "<svg/>", layers: [] };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  await sendChat("s1", "hello");
  const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(call[1].body).toBeInstanceOf(FormData);
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- api`
Expected: FAIL (sendChat sends JSON, not FormData)

- [ ] **Step 3: Implement**

Replace `sendChat` in `web/lib/api.ts`:
```ts
export async function sendChat(
  sid: string,
  message: string,
  file?: File,
): Promise<ChatResult> {
  const fd = new FormData();
  fd.append("message", message);
  if (file) fd.append("file", file);
  return asJson<ChatResult>(
    await fetch(`${BASE}/sessions/${sid}/chat`, { method: "POST", body: fd }),
  );
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- api`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/api.ts web/__tests__/api.test.ts
git commit -m "feat(web): sendChat sends multipart with optional attachment"
```

---

## Task 8: Attach button in ChatPanel

**Files:** Modify `web/components/ChatPanel.tsx`, `web/app/globals.css`, `web/__tests__/ChatPanel.test.tsx`

- [ ] **Step 1: Write the failing test**

Append to `web/__tests__/ChatPanel.test.tsx`:
```tsx
it("shows the attached filename and submits message + file", async () => {
  const onSend = vi.fn();
  render(<ChatPanel messages={[]} onSend={onSend} busy={false} />);
  const file = new File(["x"], "chair.dxf", { type: "application/dxf" });
  const input = screen.getByLabelText(/attach dxf/i) as HTMLInputElement;
  await userEvent.upload(input, file);
  expect(screen.getByText("chair.dxf")).toBeTruthy();
  await userEvent.type(screen.getByPlaceholderText(/describe a change/i), "place it");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  expect(onSend).toHaveBeenCalledWith("place it", file);
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- ChatPanel`
Expected: FAIL (no attach input; onSend signature differs)

- [ ] **Step 3: Implement**

Update `web/components/ChatPanel.tsx` so `onSend` takes an optional file and the form has an attach control. Change the prop type and component body:
```tsx
export function ChatPanel({
  messages,
  onSend,
  busy,
}: {
  messages: Msg[];
  onSend: (m: string, file?: File) => void;
  busy: boolean;
}) {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, busy]);

  return (
    <div className="chat">
      <div className="panel-head">
        <span className="dot" />
        Assistant
      </div>

      <div className="chat-scroll" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "msg msg-user" : "msg msg-ai"}>
            {m.text}
          </div>
        ))}
        {busy && (
          <div className="typing" aria-label="Assistant is working">
            <span />
            <span />
            <span />
          </div>
        )}
      </div>

      {file && (
        <div className="attach-chip">
          <span>{file.name}</span>
          <button type="button" aria-label="Remove attachment" onClick={() => setFile(null)}>
            ×
          </button>
        </div>
      )}

      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          if ((text.trim() || file) && !busy) {
            onSend(text.trim(), file ?? undefined);
            setText("");
            setFile(null);
          }
        }}
      >
        <label className="attach-btn" aria-label="Attach DXF">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M21 11.5 12.5 20a5 5 0 0 1-7-7l8-8a3.5 3.5 0 0 1 5 5l-8 8a2 2 0 0 1-3-3l7.5-7.5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <input
            type="file"
            accept=".dxf"
            className="vh"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setFile(f);
              e.target.value = "";
            }}
          />
        </label>
        <input
          className="chat-input"
          placeholder="Describe a change…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={busy}
        />
        <button type="submit" className="send-btn" aria-label="Send" disabled={busy}>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M5 12h14M13 6l6 6-6 6"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </form>
    </div>
  );
}
```
Add to `web/app/globals.css`:
```css
.attach-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 12px;
  padding: 6px 10px;
  font-size: 12.5px;
  color: var(--ink-soft);
  background: var(--accent-soft);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
}
.attach-chip button {
  margin-left: auto;
  border: none;
  background: transparent;
  font-size: 15px;
  line-height: 1;
  color: var(--ink-soft);
}
.attach-btn {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  border-radius: var(--radius-sm);
  color: var(--ink-soft);
  background: var(--panel-2);
  border: 1px solid var(--line-strong);
  cursor: pointer;
}
.attach-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- ChatPanel`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/components/ChatPanel.tsx web/app/globals.css web/__tests__/ChatPanel.test.tsx
git commit -m "feat(web): attach a DXF in the chat input"
```

---

## Task 9: Thread the attached file through the page

**Files:** Modify `web/app/page.tsx`

- [ ] **Step 1: Update handleSend**

In `web/app/page.tsx`, change `handleSend` to accept and forward the file:
```tsx
  async function handleSend(msg: string, file?: File) {
    if (!sid) return;
    const label = file ? `${msg || "Place this"}  📎 ${file.name}` : msg;
    setMessages((m) => [...m, { role: "user", text: label }]);
    setBusy(true);
    setError(null);
    try {
      const res = await sendChat(sid, msg, file);
      setSvg(res.svg);
      setLayers(res.layers);
      setMessages((m) => [...m, { role: "assistant", text: res.reply }]);
      setChanges((c) => [...c, ...res.changes]);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }
```

- [ ] **Step 2: Verify build + all web tests**

Run: `cd web && npm test && npm run build`
Expected: PASS, build succeeds.

- [ ] **Step 3: Commit**

```bash
git add web/app/page.tsx
git commit -m "feat(web): forward chat attachment to the engine"
```

- [ ] **Step 4: Manual end-to-end**

Restart engine, refresh app. Upload a base plan, then attach a small furniture `.dxf` in chat with "place this near the entrance". Confirm it appears at a sensible spot and scale; then "rotate it 90 degrees" and "move it 1m left"; then download and reopen the DXF to confirm the block is present.

---

## Self-Review notes (addressed)

- **Spec coverage:** attach+import (T2, T6), place via NL (T3, T5), unit scale baked at import (T2), persists for session (T6 `_components`), move/delete reuse existing + rotate (T3, T5), query reports block (T4), UI attach button + chip (T8), multipart client (T7), error handling: 422 bad/empty attachment (T2, T6), ComponentNotFound surfaced to AI (T5 dispatch). All covered.
- **Placeholder scan:** all steps contain concrete code/commands.
- **Type consistency:** `place_component`/`rotate_entity` arg names (`x_m`, `y_m`, `rotation_deg`, `scale`, `angle_deg`) match between `edits`, `tools` schemas, and `dispatch`; `run_agent(..., components=[...])` matches between `agent.py`, tests, and `main.py`; web `onSend(msg, file?)` and `sendChat(sid, message, file?)` match across `ChatPanel`, `page.tsx`, `api.ts`.
- **Verified API:** `Importer.import_modelspace(target_layout=block)` + `Matrix44.scale` baking confirmed via spike; `add_blockref` rotation/xscale confirmed.
