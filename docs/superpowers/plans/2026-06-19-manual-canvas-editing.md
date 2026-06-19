# Manual Drag-to-Edit on the Canvas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user select a session-added item on the canvas and move it (drag), rotate it (handle, 15° snap), delete it (key), and nudge it (arrows) — applied through the existing `ezdxf` ops, with live re-render and working Undo, no AI involved.

**Architecture:** The engine returns a `view` (the verified linear world↔SVG map) with every render, tracks which handles the user/agent added (`_editable`), exposes them via `GET /selectables`, and applies one edit via `POST /edit` that reuses `tools.dispatch`. The Next.js viewer draws an overlay `<svg>` sharing the base viewBox; the browser's `getScreenCTM()` handles screen↔viewBox, and a pure `viewmap.ts` handles world↔svg and svg-delta→meters.

**Tech Stack:** Python 3.12, FastAPI, ezdxf (`ezdxf.bbox.extents`), pytest; Next.js, TypeScript, Vitest + React Testing Library.

---

## File Structure

```
engine/app/
  view.py        # NEW: svg_view(doc) -> {world, viewBox, meters_per_unit}
  main.py        # + _editable registry, _record_changes, /selectables, /edit, view in responses
engine/tests/
  test_view.py   # NEW
  test_api.py    # + selectables + edit endpoints
web/
  lib/viewmap.ts # NEW: pure world<->svg + svg-delta->meters
  lib/api.ts     # + View type, getSelectables, manualEdit, view on results
  components/SvgViewer.tsx   # overlay svg + select/drag/rotate/delete/nudge
  app/page.tsx               # selectables + view state, onEdit wiring
  app/globals.css            # selection box / handle styles
  __tests__/viewmap.test.ts  # NEW
  __tests__/api.test.ts      # + getSelectables/manualEdit
  __tests__/SvgViewer.test.tsx # + selection/drag/delete/nudge
```

Work happens on the existing `feat/cad-designer` branch. Engine commands from `cad-designer/engine` via `.venv/bin/...`; web commands from `cad-designer/web`.

---

## Conventions to follow (read before starting)

- ezdxf `SVGBackend` + `Page(0,0)` emits `viewBox="0 0 VW VH"` where the longer world side
  maps to 1,000,000, aspect preserved, origin (0,0), **Y-flipped**. Verified: a 10×8 world
  → `0 0 1000000 800000`. So scale `s = 1_000_000 / max(world_w, world_h)` and
  `VW = world_w * s`, `VH = world_h * s`.
- `units.meters_per_unit(doc)` → meters per drawing unit (1.0 meters fixture, 0.001 mm).
- `tools.dispatch(doc, name, args)` already implements `move_entity` (`dx_m`,`dy_m`→units),
  `rotate_entity` (`angle_deg`), `delete_entity` (`handle`), returning `{result, change, error}`.
- Change records: `{op, handle, before, after, summary}`.
- `sample_doc` fixture: 10×8 m WALLS plan with a `CASH COUNTER` text and a FIXTURES line;
  extents `min=(0,0)`, `max=(10,8)`.
- Web has no `src/` dir: files live at `web/lib`, `web/components`, `web/app`, `web/__tests__`.

---

# PHASE A — ENGINE

## Task 1: `view.py` — the world↔SVG map

**Files:**
- Create: `engine/app/view.py`, `engine/tests/test_view.py`

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_view.py`:
```python
import re

import ezdxf

from app.render import render_svg
from app.view import svg_view


def test_view_matches_rendered_viewbox(sample_doc):
    doc = sample_doc["doc"]
    v = svg_view(doc)
    assert v is not None
    # world extents of the fixture
    assert [round(c) for c in v["world"]] == [0, 0, 10, 8]
    assert v["meters_per_unit"] == 1.0
    # computed viewBox matches the one ezdxf actually rendered
    svg = render_svg(doc)
    vb = re.search(r'viewBox="([^"]+)"', svg[:400]).group(1)
    rendered = [round(float(x)) for x in vb.split()]
    assert [round(x) for x in v["viewBox"]] == rendered


def test_view_aspect_preserved(sample_doc):
    v = svg_view(sample_doc["doc"])
    _, _, vw, vh = v["viewBox"]
    assert abs((vw / vh) - (10 / 8)) < 1e-6
    assert max(vw, vh) == 1_000_000


def test_view_empty_modelspace():
    assert svg_view(ezdxf.new("R2010")) is None
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_view.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.view'`

- [ ] **Step 3: Implement**

`engine/app/view.py`:
```python
from ezdxf.document import Drawing

from app import units
from app.space import drawing_bounds

_VIEWBOX_MAX = 1_000_000.0


def svg_view(doc: Drawing) -> dict | None:
    """The linear map between the rendered SVG's viewBox and world (drawing-unit)
    coordinates. Mirrors ezdxf SVGBackend + auto Page(0,0): longer world side ->
    1,000,000, aspect preserved, origin (0,0), Y-flipped. Returns None if empty."""
    bounds = drawing_bounds(doc)
    if bounds is None:
        return None
    min_x, min_y, max_x, max_y = bounds
    world_w = max_x - min_x
    world_h = max_y - min_y
    longest = max(world_w, world_h)
    if longest <= 0:
        return None
    s = _VIEWBOX_MAX / longest
    return {
        "world": [min_x, min_y, max_x, max_y],
        "viewBox": [0.0, 0.0, world_w * s, world_h * s],
        "meters_per_unit": units.meters_per_unit(doc),
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_view.py -v`
Expected: PASS. If `viewBox` rounding disagrees, print both values and adjust the
rounding in the test (the scale formula matches ezdxf; only float formatting can differ).

- [ ] **Step 5: Commit**

```bash
git add engine/app/view.py engine/tests/test_view.py
git commit -m "feat(engine): svg_view world<->viewBox mapping"
```

---

## Task 2: Editable registry + `/selectables`

**Files:**
- Modify: `engine/app/main.py`, `engine/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_api.py`:
```python
def test_selectables_lists_added_excludes_base(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)

    # simulate the agent adding a wall (records its handle as editable)
    def fake_run_agent(**kwargs):
        from app import edits

        c = edits.add_wall(kwargs["doc"], 0, 0, 3, 0, layer="NEW")
        return {"reply": "added", "changes": [c], "entrance": None}

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())
    r = client.post(f"/sessions/{sid}/chat", data={"message": "add a wall"})
    added_handle = r.json()["changes"][0]["handle"]

    s = client.get(f"/sessions/{sid}/selectables")
    assert s.status_code == 200
    body = s.json()
    handles = {e["handle"] for e in body["selectables"]}
    assert added_handle in handles
    # the base-shell WALLS polyline from the fixture is NOT selectable
    assert all(e["handle"] != sample_bytes_wall_handle(main.store.get(sid)) for e in body["selectables"])
    assert body["view"] is not None
    one = next(e for e in body["selectables"] if e["handle"] == added_handle)
    assert "bbox" in one and len(one["bbox"]) == 4 and "label" in one


def sample_bytes_wall_handle(doc):
    # the fixture's base WALLS polyline (added before any session edit)
    for e in doc.modelspace():
        if e.dxf.layer == "WALLS":
            return e.dxf.handle
    return None
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_api.py -k selectables -v`
Expected: FAIL (404 / no `/selectables` route)

- [ ] **Step 3: Implement**

In `engine/app/main.py`:

(a) add `view` import and `_editable` registry next to `_orientation`:
```python
from app import components, space, units, view as view_mod
```
```python
# session_id -> set of handles the user/agent added (selectable for manual edit)
_editable: dict[str, set[str]] = {}

_ADD_OPS = {"place_component", "add_text_label", "add_wall"}


def _record_changes(sid: str, changes: list[dict]) -> None:
    bucket = _editable.setdefault(sid, set())
    for c in changes:
        op, handle = c.get("op"), c.get("handle")
        if op in _ADD_OPS and handle:
            bucket.add(handle)
        elif op == "delete_entity" and handle:
            bucket.discard(handle)


def _selectable_entities(doc, sid: str) -> list[dict]:
    from ezdxf.bbox import extents

    out = []
    for handle in list(_editable.get(sid, set())):
        e = doc.entitydb.get(handle)
        if e is None or not e.is_alive:
            _editable[sid].discard(handle)
            continue
        bb = extents([e])
        if not bb.has_data:
            continue
        if e.dxftype() == "INSERT":
            label = e.dxf.name
        elif e.dxftype() in ("TEXT", "MTEXT"):
            label = e.dxf.text if e.dxftype() == "TEXT" else e.text
        else:
            label = e.dxftype()
        out.append({
            "handle": handle,
            "type": e.dxftype(),
            "label": label,
            "bbox": [bb.extmin.x, bb.extmin.y, bb.extmax.x, bb.extmax.y],
        })
    return out
```

(b) record changes in `chat`: right after `if out.get("entrance"): _orientation[sid] = out["entrance"]`, add:
```python
    _record_changes(sid, out["changes"])
```

(c) add the endpoint (after the `chat` handler):
```python
@app.get("/sessions/{sid}/selectables")
def selectables(sid: str) -> dict:
    doc = store.get(sid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    return {"selectables": _selectable_entities(doc, sid), "view": view_mod.svg_view(doc)}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_api.py -k selectables -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/main.py engine/tests/test_api.py
git commit -m "feat(engine): track added entities and expose /selectables"
```

---

## Task 3: `POST /edit` (one tool, no AI) + `view` in render responses

**Files:**
- Modify: `engine/app/main.py`, `engine/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_api.py`:
```python
def _make_session_with_component(monkeypatch):
    _fresh_store()
    from app import edits

    # build a base session and place a component via the fake agent so it's editable
    sid = main.store.create(open("/dev/stdin").read().encode()) if False else None
    return sid


def test_edit_move_converts_meters_and_returns_view(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    from app import edits

    # add a movable line and register it as editable
    c = edits.add_wall(main.store.get(sid), 2, 2, 4, 2, layer="NEW")
    main._editable.setdefault(sid, set()).add(c["handle"])
    h = c["handle"]

    r = client.post(
        f"/sessions/{sid}/edit",
        json={"name": "move_entity", "args": {"handle": h, "dx_m": 1.0, "dy_m": 0.0}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["change"]["op"] == "move_entity"
    assert body["view"] is not None and "selectables" in body
    moved = main.store.get(sid).entitydb[h]
    assert abs(moved.dxf.start.x - 3.0) < 1e-6  # 2 + 1m (meters fixture)


def test_edit_delete_drops_from_selectables(sample_bytes):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    from app import edits

    c = edits.add_wall(main.store.get(sid), 0, 0, 1, 1, layer="NEW")
    main._editable.setdefault(sid, set()).add(c["handle"])
    h = c["handle"]
    r = client.post(
        f"/sessions/{sid}/edit", json={"name": "delete_entity", "args": {"handle": h}}
    )
    assert r.status_code == 200
    assert all(e["handle"] != h for e in r.json()["selectables"])


def test_edit_rejects_unknown_op(sample_bytes):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    r = client.post(f"/sessions/{sid}/edit", json={"name": "frobnicate", "args": {}})
    assert r.status_code == 400


def test_edit_bad_handle_is_422_and_no_change(sample_bytes):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    before = len(list(main.store.get(sid).modelspace()))
    r = client.post(
        f"/sessions/{sid}/edit",
        json={"name": "move_entity", "args": {"handle": "DEAD", "dx_m": 1, "dy_m": 0}},
    )
    assert r.status_code == 422
    assert len(list(main.store.get(sid).modelspace())) == before
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_api.py -k edit -v`
Expected: FAIL (no `/edit` route)

- [ ] **Step 3: Implement**

In `engine/app/main.py`, add a request model near `UnitsRequest`:
```python
class EditRequest(BaseModel):
    name: str
    args: dict
```
Add the endpoint (after `selectables`):
```python
from app.tools import dispatch as _dispatch

_MANUAL_OPS = {"move_entity", "rotate_entity", "delete_entity"}


@app.post("/sessions/{sid}/edit")
def edit(sid: str, req: EditRequest) -> dict:
    doc = store.get(sid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    if req.name not in _MANUAL_OPS:
        raise HTTPException(status_code=400, detail=f"Unsupported edit op: {req.name}")

    store.snapshot(sid)
    out = _dispatch(doc, req.name, req.args)
    if out["error"]:
        store.undo(sid)  # revert the snapshot; nothing changed
        raise HTTPException(status_code=422, detail=out["error"])

    _record_changes(sid, [out["change"]])
    current = store.get(sid)
    return {
        "change": out["change"],
        "svg": render_svg(current),
        "view": view_mod.svg_view(current),
        "layers": list_layers(current),
        "selectables": _selectable_entities(current, sid),
    }
```
Add `"view": view_mod.svg_view(doc)` to the **upload** response and the **chat** response
and the **undo** response. For upload (`create_session`), change the return to:
```python
    return {
        "session_id": sid,
        "svg": render_svg(doc),
        "summary": _summary(doc),
        "view": view_mod.svg_view(doc),
    }
```
For `chat`, add `"view": view_mod.svg_view(current),` to its returned dict. For `undo`,
change its return to include the view:
```python
    current = store.get(sid)
    return {"svg": render_svg(current), "layers": list_layers(current),
            "view": view_mod.svg_view(current)}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/ -q`
Expected: PASS (all engine tests).

- [ ] **Step 5: Commit**

```bash
git add engine/app/main.py engine/tests/test_api.py
git commit -m "feat(engine): manual /edit endpoint (one dispatch op) + view in responses"
```

---

# PHASE B — WEB

## Task 4: `viewmap.ts` — pure coordinate helpers

**Files:**
- Create: `web/lib/viewmap.ts`, `web/__tests__/viewmap.test.ts`

- [ ] **Step 1: Write the failing tests**

`web/__tests__/viewmap.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { worldToSvg, svgRectFromBBox, svgDeltaToMeters, type View } from "../lib/viewmap";

// 10 x 8 world (meters), viewBox 1,000,000 x 800,000, scale s = 100000
const view: View = {
  world: [0, 0, 10, 8],
  viewBox: [0, 0, 1_000_000, 800_000],
  meters_per_unit: 1.0,
};

it("worldToSvg maps origin to top-left (Y flipped)", () => {
  expect(worldToSvg(view, 0, 0)).toEqual([0, 800_000]); // world y=0 is bottom -> svg bottom
  expect(worldToSvg(view, 0, 8)).toEqual([0, 0]); // world y=8 (top) -> svg y=0
  expect(worldToSvg(view, 10, 8)).toEqual([1_000_000, 0]);
});

it("svgRectFromBBox builds an svg-space rect", () => {
  const r = svgRectFromBBox(view, [2, 2, 4, 3]); // 2 wide, 1 tall in world
  expect(r.width).toBe(200_000);
  expect(r.height).toBe(100_000);
  expect(r.x).toBe(200_000);
  expect(r.y).toBe(500_000); // top edge y=3 -> (8-3)*1e5
});

it("svgDeltaToMeters inverts scale with Y flip", () => {
  // moving +100000 svg-x, +100000 svg-y => +1 world-x, -1 world-y (meters here = units)
  expect(svgDeltaToMeters(view, 100_000, 100_000)).toEqual([1, -1]);
});

it("svgDeltaToMeters honors meters_per_unit (mm)", () => {
  const mm: View = { world: [0, 0, 10000, 8000], viewBox: [0, 0, 1_000_000, 800_000], meters_per_unit: 0.001 };
  // s = 100 svg per unit; 100000 svg-x => 1000 units => 1 m
  expect(svgDeltaToMeters(mm, 100_000, 0)[0]).toBeCloseTo(1, 6);
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- viewmap`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement**

`web/lib/viewmap.ts`:
```ts
export type View = {
  world: [number, number, number, number]; // xmin,ymin,xmax,ymax (drawing units)
  viewBox: [number, number, number, number]; // 0,0,VW,VH
  meters_per_unit: number;
};

function scale(view: View): number {
  const [xmin, , xmax] = view.world;
  return view.viewBox[2] / (xmax - xmin);
}

export function worldToSvg(view: View, wx: number, wy: number): [number, number] {
  const [xmin, ymin, , ymax] = view.world;
  const s = scale(view);
  return [(wx - xmin) * s, (ymax - wy) * s];
}

export function svgRectFromBBox(
  view: View,
  bbox: [number, number, number, number],
): { x: number; y: number; width: number; height: number } {
  const [x0, y0, x1, y1] = bbox;
  const [sx0, sy1] = worldToSvg(view, x0, y1); // top-left in svg (world top = y1)
  const [sx1, sy0] = worldToSvg(view, x1, y0);
  return { x: Math.min(sx0, sx1), y: Math.min(sy0, sy1), width: Math.abs(sx1 - sx0), height: Math.abs(sy0 - sy1) };
}

export function svgDeltaToMeters(view: View, dxSvg: number, dySvg: number): [number, number] {
  const s = scale(view);
  const dxUnits = dxSvg / s;
  const dyUnits = -dySvg / s; // Y flip
  return [dxUnits * view.meters_per_unit, dyUnits * view.meters_per_unit];
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- viewmap`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/viewmap.ts web/__tests__/viewmap.test.ts
git commit -m "feat(web): pure world<->svg viewmap helpers"
```

---

## Task 5: API client — `getSelectables`, `manualEdit`, `view` types

**Files:**
- Modify: `web/lib/api.ts`, `web/__tests__/api.test.ts`

- [ ] **Step 1: Write the failing tests**

Append to `web/__tests__/api.test.ts`:
```ts
it("getSelectables returns selectables and view", async () => {
  const body = { selectables: [{ handle: "A", type: "INSERT", label: "chair", bbox: [0, 0, 1, 1] }], view: null };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const { getSelectables } = await import("../lib/api");
  const res = await getSelectables("s1");
  expect(res.selectables[0].handle).toBe("A");
  const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(call[0]).toContain("/sessions/s1/selectables");
});

it("manualEdit posts name+args as json", async () => {
  const body = { change: { op: "move_entity" }, svg: "<svg/>", view: null, layers: [], selectables: [] };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const { manualEdit } = await import("../lib/api");
  const res = await manualEdit("s1", "move_entity", { handle: "A", dx_m: 1, dy_m: 0 });
  expect(res.change.op).toBe("move_entity");
  const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(call[0]).toContain("/sessions/s1/edit");
  expect(JSON.parse(call[1].body)).toEqual({ name: "move_entity", args: { handle: "A", dx_m: 1, dy_m: 0 } });
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- api`
Expected: FAIL (exports missing)

- [ ] **Step 3: Implement**

In `web/lib/api.ts`, add the `View`/`Selectable` types and re-export, and the two
functions. Also add `view` to the existing result types:
```ts
export type View = {
  world: [number, number, number, number];
  viewBox: [number, number, number, number];
  meters_per_unit: number;
};
export type Selectable = {
  handle: string;
  type: string;
  label: string;
  bbox: [number, number, number, number];
};
export type EditResult = {
  change: Change;
  svg: string;
  view: View | null;
  layers: Layer[];
  selectables: Selectable[];
};

export async function getSelectables(
  sid: string,
): Promise<{ selectables: Selectable[]; view: View | null }> {
  return asJson(await fetch(`${BASE}/sessions/${sid}/selectables`));
}

export async function manualEdit(
  sid: string,
  name: string,
  args: Record<string, unknown>,
): Promise<EditResult> {
  return asJson<EditResult>(
    await fetch(`${BASE}/sessions/${sid}/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, args }),
    }),
  );
}
```
Add `view?: View | null` to `UploadResult` and `ChatResult`, and make `undo` return
`{ svg: string; layers: Layer[]; view: View | null }`.

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- api`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/api.ts web/__tests__/api.test.ts
git commit -m "feat(web): getSelectables + manualEdit clients and view types"
```

---

## Task 6: SvgViewer overlay — select, drag, rotate, delete, nudge

**Files:**
- Modify: `web/components/SvgViewer.tsx`, `web/app/globals.css`, `web/__tests__/SvgViewer.test.tsx`

This is the largest task. The overlay `<svg>` sits inside the same transform wrapper as the
base SVG and uses the same `viewBox`, so its coordinate space matches the drawing.
`getScreenCTM()` converts pointer screen coords to overlay-svg coords.

- [ ] **Step 1: Write the failing tests**

`web/__tests__/SvgViewer.test.tsx` (replace the file's contents, keeping the two existing
render tests and adding interaction tests; the existing tests are reproduced here):
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SvgViewer } from "../components/SvgViewer";
import type { View, Selectable } from "../lib/api";

const view: View = { world: [0, 0, 10, 8], viewBox: [0, 0, 1_000_000, 800_000], meters_per_unit: 1.0 };
const sel: Selectable = { handle: "H1", type: "INSERT", label: "chair", bbox: [4, 3, 6, 5] };

// jsdom has no getScreenCTM; identity CTM means screen coords == svg coords.
beforeEach(() => {
  // @ts-expect-error test shim
  SVGElement.prototype.getScreenCTM = function () {
    return { inverse: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }) };
  };
  // @ts-expect-error test shim
  SVGSVGElement.prototype.createSVGPoint = function () {
    const p = { x: 0, y: 0, matrixTransform: (m: DOMMatrix) => ({ x: p.x, y: p.y }) };
    return p;
  };
});

it("renders the provided svg markup", () => {
  const { container } = render(<SvgViewer svg='<svg data-testid="dwg"></svg>' />);
  expect(container.querySelector('[data-testid="dwg"]')).not.toBeNull();
});

it("shows a placeholder when svg is empty", () => {
  render(<SvgViewer svg="" />);
  expect(screen.getByText(/no drawing/i)).toBeTruthy();
});

it("selecting an item via the overlay calls onSelect", () => {
  const onSelect = vi.fn();
  render(
    <SvgViewer svg="<svg/>" view={view} selectables={[sel]} onSelect={onSelect} onEdit={vi.fn()} />,
  );
  const box = screen.getByTestId("sel-H1");
  fireEvent.pointerDown(box);
  expect(onSelect).toHaveBeenCalledWith("H1");
});

it("Delete key on a selected item calls onEdit delete_entity", () => {
  const onEdit = vi.fn().mockResolvedValue(undefined);
  render(
    <SvgViewer svg="<svg/>" view={view} selectables={[sel]} selected="H1" onEdit={onEdit} onSelect={vi.fn()} />,
  );
  fireEvent.keyDown(window, { key: "Delete" });
  expect(onEdit).toHaveBeenCalledWith("delete_entity", { handle: "H1" });
});

it("arrow key nudges by 0.1m via move_entity", () => {
  const onEdit = vi.fn().mockResolvedValue(undefined);
  render(
    <SvgViewer svg="<svg/>" view={view} selectables={[sel]} selected="H1" onEdit={onEdit} onSelect={vi.fn()} />,
  );
  fireEvent.keyDown(window, { key: "ArrowRight" });
  expect(onEdit).toHaveBeenCalledWith("move_entity", { handle: "H1", dx_m: 0.1, dy_m: 0 });
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- SvgViewer`
Expected: FAIL (props/overlay not implemented)

- [ ] **Step 3: Implement**

Rewrite `web/components/SvgViewer.tsx` to accept the new optional props and render the
overlay. Keep the existing pan/zoom and controls. Full file:
```tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { svgRectFromBBox, svgDeltaToMeters, type View } from "../lib/viewmap";
import type { Selectable } from "../lib/api";

type Props = {
  svg: string;
  view?: View | null;
  selectables?: Selectable[];
  selected?: string | null;
  onSelect?: (handle: string | null) => void;
  onEdit?: (name: string, args: Record<string, unknown>) => void;
};

export function SvgViewer({
  svg,
  view = null,
  selectables = [],
  selected = null,
  onSelect,
  onEdit,
}: Props) {
  const [scale, setScale] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const pan = useRef<{ x: number; y: number } | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ handle: string; startX: number; startY: number } | null>(null);

  // keyboard: delete + arrow nudge on the selected entity
  useEffect(() => {
    if (!selected || !onEdit) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        onEdit!("delete_entity", { handle: selected });
      } else if (e.key.startsWith("Arrow")) {
        e.preventDefault();
        const step = 0.1;
        const d: Record<string, [number, number]> = {
          ArrowRight: [step, 0], ArrowLeft: [-step, 0],
          ArrowUp: [0, step], ArrowDown: [0, -step],
        };
        const [dx, dy] = d[e.key] ?? [0, 0];
        onEdit!("move_entity", { handle: selected, dx_m: dx, dy_m: dy });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected, onEdit]);

  if (!svg) {
    return (
      <div className="empty">
        <div className="empty-icon">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M3 9h18M9 21V9M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <h2>No drawing loaded</h2>
        <p>Upload a <code>.dxf</code> floor plan to view it here, then describe changes in plain language on the right.</p>
      </div>
    );
  }

  // map a pointer event to overlay-svg coordinates via the browser CTM
  function toSvg(e: React.PointerEvent | PointerEvent): { x: number; y: number } {
    const svgEl = overlayRef.current!;
    const pt = svgEl.createSVGPoint();
    pt.x = (e as PointerEvent).clientX;
    pt.y = (e as PointerEvent).clientY;
    const ctm = svgEl.getScreenCTM();
    const local = ctm ? pt.matrixTransform(ctm.inverse()) : pt;
    return { x: local.x, y: local.y };
  }

  return (
    <>
      <div
        ref={stageRef}
        className="canvas-stage"
        onWheel={(e) => setScale((s) => Math.min(20, Math.max(0.05, s - e.deltaY * 0.0015)))}
        onMouseDown={(e) => (pan.current = { x: e.clientX - pos.x, y: e.clientY - pos.y })}
        onMouseUp={() => (pan.current = null)}
        onMouseLeave={() => (pan.current = null)}
        onMouseMove={(e) => {
          if (pan.current) setPos({ x: e.clientX - pan.current.x, y: e.clientY - pan.current.y });
        }}
      >
        <div
          style={{ transform: `translate(${pos.x}px, ${pos.y}px) scale(${scale})`, transformOrigin: "0 0", width: "100%", height: "100%", position: "relative" }}
        >
          <div style={{ width: "100%", height: "100%" }} dangerouslySetInnerHTML={{ __html: svg }} />
          {view && (
            <svg
              ref={overlayRef}
              className="edit-overlay"
              viewBox={view.viewBox.join(" ")}
              preserveAspectRatio="xMidYMid meet"
              style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
            >
              {selectables.map((s) => {
                const r = svgRectFromBBox(view, s.bbox);
                const isSel = s.handle === selected;
                return (
                  <rect
                    key={s.handle}
                    data-testid={`sel-${s.handle}`}
                    x={r.x}
                    y={r.y}
                    width={r.width}
                    height={r.height}
                    className={isSel ? "sel-box sel-box-active" : "sel-box"}
                    onPointerDown={(e) => {
                      e.stopPropagation();
                      onSelect?.(s.handle);
                      const p = toSvg(e);
                      dragRef.current = { handle: s.handle, startX: p.x, startY: p.y };
                      (e.target as Element).setPointerCapture?.(e.pointerId);
                    }}
                    onPointerUp={(e) => {
                      const d = dragRef.current;
                      dragRef.current = null;
                      if (!d || !view || !onEdit) return;
                      const p = toSvg(e);
                      const [dx_m, dy_m] = svgDeltaToMeters(view, p.x - d.startX, p.y - d.startY);
                      if (dx_m !== 0 || dy_m !== 0) onEdit("move_entity", { handle: d.handle, dx_m, dy_m });
                    }}
                  />
                );
              })}
            </svg>
          )}
        </div>
      </div>

      <div className="canvas-controls">
        <button aria-label="Zoom in" onClick={() => setScale((s) => Math.min(20, s * 1.25))}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
        </button>
        <button aria-label="Zoom out" onClick={() => setScale((s) => Math.max(0.05, s * 0.8))}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
        </button>
        <button aria-label="Reset view" onClick={() => { setScale(1); setPos({ x: 0, y: 0 }); }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8m0-5v5h5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </button>
      </div>

      <div className="zoom-hint">Scroll to zoom · drag to pan · click an item to edit · {Math.round(scale * 100)}%</div>
    </>
  );
}
```
Add to `web/app/globals.css`:
```css
.edit-overlay { pointer-events: none; overflow: visible; }
.sel-box {
  pointer-events: all;
  fill: transparent;
  stroke: var(--accent);
  stroke-width: 2000;          /* svg units (~1e6 viewBox); thin on screen */
  stroke-dasharray: 6000 6000;
  cursor: move;
  opacity: 0.35;
}
.sel-box:hover { opacity: 0.7; }
.sel-box-active { opacity: 1; stroke-dasharray: none; }
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- SvgViewer`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/components/SvgViewer.tsx web/app/globals.css web/__tests__/SvgViewer.test.tsx
git commit -m "feat(web): canvas overlay with select/drag/delete/nudge"
```

---

## Task 7: Rotate handle

**Files:**
- Modify: `web/components/SvgViewer.tsx`, `web/__tests__/SvgViewer.test.tsx`

- [ ] **Step 1: Write the failing test**

Append to `web/__tests__/SvgViewer.test.tsx`:
```tsx
it("dragging the rotate handle calls onEdit rotate_entity with a snapped angle", () => {
  const onEdit = vi.fn().mockResolvedValue(undefined);
  render(
    <SvgViewer svg="<svg/>" view={view} selectables={[sel]} selected="H1" onEdit={onEdit} onSelect={vi.fn()} />,
  );
  const handle = screen.getByTestId("rotate-H1");
  fireEvent.pointerDown(handle, { clientX: 0, clientY: 0 });
  fireEvent.pointerUp(handle, { clientX: 0, clientY: 0 });
  expect(onEdit).toHaveBeenCalledWith("rotate_entity", expect.objectContaining({ handle: "H1" }));
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- SvgViewer`
Expected: FAIL (no `rotate-H1` element)

- [ ] **Step 3: Implement**

In `SvgViewer.tsx`, when an item is selected, render a rotate handle above its box and wire
it. Inside the `selectables.map`, after the `<rect>`, add (only for the selected item) a
handle circle. Replace the `selectables.map(...)` return with a fragment that includes the
handle:
```tsx
              {selectables.map((s) => {
                const r = svgRectFromBBox(view, s.bbox);
                const isSel = s.handle === selected;
                const cx = r.x + r.width / 2;
                const handleY = r.y - r.height * 0.25 - 1;
                return (
                  <g key={s.handle}>
                    <rect
                      data-testid={`sel-${s.handle}`}
                      x={r.x} y={r.y} width={r.width} height={r.height}
                      className={isSel ? "sel-box sel-box-active" : "sel-box"}
                      onPointerDown={(e) => {
                        e.stopPropagation();
                        onSelect?.(s.handle);
                        const p = toSvg(e);
                        dragRef.current = { handle: s.handle, startX: p.x, startY: p.y };
                        (e.target as Element).setPointerCapture?.(e.pointerId);
                      }}
                      onPointerUp={(e) => {
                        const d = dragRef.current;
                        dragRef.current = null;
                        if (!d || !view || !onEdit) return;
                        const p = toSvg(e);
                        const [dx_m, dy_m] = svgDeltaToMeters(view, p.x - d.startX, p.y - d.startY);
                        if (dx_m !== 0 || dy_m !== 0) onEdit("move_entity", { handle: d.handle, dx_m, dy_m });
                      }}
                    />
                    {isSel && (
                      <circle
                        data-testid={`rotate-${s.handle}`}
                        cx={cx} cy={handleY}
                        r={Math.max(r.width, r.height) * 0.06 + 3000}
                        className="rotate-handle"
                        onPointerDown={(e) => {
                          e.stopPropagation();
                          const p = toSvg(e);
                          rotRef.current = { handle: s.handle, cx, cy: r.y + r.height / 2, startX: p.x, startY: p.y };
                          (e.target as Element).setPointerCapture?.(e.pointerId);
                        }}
                        onPointerUp={(e) => {
                          const rt = rotRef.current;
                          rotRef.current = null;
                          if (!rt || !onEdit) return;
                          const p = toSvg(e);
                          const a0 = Math.atan2(rt.startY - rt.cy, rt.startX - rt.cx);
                          const a1 = Math.atan2(p.y - rt.cy, p.x - rt.cx);
                          let deg = ((a1 - a0) * 180) / Math.PI;
                          deg = Math.round(deg / 15) * 15; // snap 15°
                          onEdit("rotate_entity", { handle: rt.handle, angle_deg: deg });
                        }}
                      />
                    )}
                  </g>
                );
              })}
```
Add the rot ref near `dragRef`:
```tsx
  const rotRef = useRef<{ handle: string; cx: number; cy: number; startX: number; startY: number } | null>(null);
```
Add CSS:
```css
.rotate-handle { pointer-events: all; fill: var(--accent); cursor: grab; }
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- SvgViewer`
Expected: PASS (a zero-drag rotate yields angle_deg 0, which still calls onEdit; the test
only asserts the handle+op fire).

- [ ] **Step 5: Commit**

```bash
git add web/components/SvgViewer.tsx web/app/globals.css web/__tests__/SvgViewer.test.tsx
git commit -m "feat(web): rotate handle on the selection box"
```

---

## Task 8: Wire selection + edits into the page

**Files:**
- Modify: `web/app/page.tsx`

- [ ] **Step 1: Implement page wiring**

In `web/app/page.tsx`:

(a) import the new types/fns and add state:
```tsx
import { uploadDxf, sendChat, undo, downloadUrl, setUnits, getSelectables, manualEdit, type Change, type Layer, type View, type Selectable } from "../lib/api";
```
```tsx
  const [view, setView] = useState<View | null>(null);
  const [selectables, setSelectables] = useState<Selectable[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
```

(b) after a successful upload, set the view and load selectables:
```tsx
      setSvg(res.svg);
      setView(res.view ?? null);
      await refreshSelectables(res.session_id);
```
and add the helper:
```tsx
  async function refreshSelectables(id: string) {
    try {
      const r = await getSelectables(id);
      setSelectables(r.selectables);
      setView(r.view);
    } catch {
      /* non-fatal */
    }
  }
```

(c) in `handleSend`, after `setSvg(res.svg)`, add `setView(res.view ?? view);` and
`await refreshSelectables(sid);`. In `handleUndo`, after `setSvg(res.svg)`, add
`setView(res.view ?? null); await refreshSelectables(sid);`.

(d) add the manual-edit handler:
```tsx
  async function handleEdit(name: string, args: Record<string, unknown>) {
    if (!sid) return;
    try {
      const res = await manualEdit(sid, name, args);
      setSvg(res.svg);
      setView(res.view);
      setLayers(res.layers);
      setSelectables(res.selectables);
      setChanges((c) => [...c, res.change]);
      if (name === "delete_entity") setSelected(null);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
      await refreshSelectables(sid);
    }
  }
```

(e) pass the new props to `SvgViewer`:
```tsx
          <SvgViewer
            svg={svg}
            view={view}
            selectables={selectables}
            selected={selected}
            onSelect={setSelected}
            onEdit={handleEdit}
          />
```

- [ ] **Step 2: Verify build + all web tests**

Run: `cd web && npm test && npm run build`
Expected: PASS, build succeeds.

- [ ] **Step 3: Commit**

```bash
git add web/app/page.tsx
git commit -m "feat(web): wire canvas selection and manual edits into the editor page"
```

---

## Task 9: Manual end-to-end verification

**Files:** none (manual).

- [ ] **Step 1: Restart engine + open the app**

```bash
lsof -ti :8000 | xargs kill 2>/dev/null
cd engine && .venv/bin/uvicorn app.main:app --reload --port 8000 > /tmp/cad-engine.log 2>&1 &
# web already runs on :3000 (npm run dev)
```

- [ ] **Step 2: Place, then edit manually**

Upload BASE CAD (set units to mm first), attach + place the furniture at the back. Then:
click the furniture's selection box → drag it inward → confirm it moves and the SVG updates.
Press an arrow key → confirm a 0.1 m nudge. Drag the rotate handle → confirm it rotates.
Press Delete → confirm it disappears and leaves the selection list. Click **Undo** → confirm
the last manual edit reverts.

- [ ] **Step 3: Note results.** No commit (manual step).

---

## Self-Review notes (addressed)

- **Spec coverage:** view map (T1); editable registry + `/selectables` (T2); `/edit` via
  dispatch + `view` in upload/chat/undo (T3); pure viewmap (T4); clients + types (T5);
  overlay select/drag/delete/nudge (T6); rotate handle (T7); page wiring incl. refresh after
  upload/chat/undo/edit (T8); manual E2E (T9). Locked base shell = only `_editable` handles
  listed (T2). Undo covers manual edits = `/edit` snapshots (T3). All covered.
- **No placeholders:** every step has concrete code/commands.
- **Type consistency:** `View` ({world, viewBox, meters_per_unit}) identical across
  `view.py`, `viewmap.ts`, `api.ts`, and `SvgViewer` props; `Selectable.bbox` (drawing
  units) consistent engine↔web; `manualEdit(sid,name,args)` ↔ `EditRequest{name,args}` ↔
  `/edit`; `onEdit(name,args)` calls match the dispatch op names (`move_entity`,
  `rotate_entity`, `delete_entity`) and their arg keys (`handle`, `dx_m`, `dy_m`,
  `angle_deg`).
- **Known risks:** (1) jsdom lacks `getScreenCTM`/`createSVGPoint`; T6 shims them with an
  identity CTM so interaction tests run — real browsers use the true CTM. (2) selection-box
  stroke widths are in viewBox units (~1e6 space); values chosen to read as thin on screen,
  to be eyeballed in T9 and adjusted if needed. (3) the `view` scale assumes the verified
  uniform-aspect viewBox (no margins); T1 asserts the computed viewBox equals the rendered
  one, catching any ezdxf change.
```
