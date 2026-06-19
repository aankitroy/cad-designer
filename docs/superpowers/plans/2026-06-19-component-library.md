# Component Library (left panel) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A searchable left panel of the fixed DXF component library with cached thumbnails; dragging a component onto the canvas places it (centered, unit-scaled) at the drop point as a normal selectable item.

**Architecture:** A new `library.py` lists a component folder (env `CAD_LIBRARY_DIR`). Engine endpoints serve the catalog, a cached per-component SVG thumbnail (via the existing renderer), and a place-from-library op that lazily `import_as_block`s the file once per session then `place_component`s it centered at the drop point (reusing the center-align + unit-scale fixes, returning the same `EditResult` shape as `/edit`). The viewer accepts a drop, converts the drop point to world meters via a new `viewmap.svgToWorldMeters`, and a left `LibraryPanel` provides search + draggable thumbnail rows.

**Tech Stack:** Python 3.12, FastAPI, ezdxf, pytest; Next.js, TypeScript, Vitest + React Testing Library.

---

## File Structure

```
engine/app/
  library.py     # NEW: list_components, component_path (env CAD_LIBRARY_DIR)
  main.py        # + /library, /library/{id}/thumbnail.svg, /sessions/{id}/library/place
engine/tests/
  test_library.py  # NEW
  test_api.py      # + library endpoints
web/
  lib/viewmap.ts   # + svgToWorldMeters
  lib/api.ts       # + LibraryItem, getLibrary, thumbnailUrl, placeFromLibrary
  components/LibraryPanel.tsx   # NEW: search + draggable thumbnails
  components/SvgViewer.tsx      # + onDropComponent drop handling
  app/page.tsx                  # + left column, load library, wire drop
  app/globals.css               # + left panel / thumbnail styles
  __tests__/viewmap.test.ts     # + svgToWorldMeters
  __tests__/api.test.ts         # + getLibrary/placeFromLibrary
  __tests__/LibraryPanel.test.tsx  # NEW
  __tests__/SvgViewer.test.tsx     # + drop test
```

Work on the existing `feat/cad-designer` branch. Engine commands from `cad-designer/engine`
via `.venv/bin/...`; web from `cad-designer/web`.

---

## Conventions to follow (read before starting)

- `sessions._read_dxf(bytes)` loads DXF in recover mode (handles the real-CAD quirks).
- `components.import_as_block(doc, dxf_bytes, filename) -> block_name` imports + unit-scales;
  raises `ValueError` on empty/garbage.
- `edits.place_component(doc, name, x, y, rotation_deg=0, scale=1.0, layer="0")` centers the
  block on (x,y) and returns a Change.
- `tools.dispatch` / `_record_changes` / `_selectable_entities` / `view_mod.svg_view` already
  exist in `main.py`; the `/edit` endpoint returns `{change, svg, view, layers, selectables}`.
- `_components: dict[str, list[str]]` tracks imported block names per session.
- Web has no `src/`: files at `web/lib`, `web/components`, `web/app`, `web/__tests__`.
- `viewmap.View = {world:[xmin,ymin,xmax,ymax], viewBox:[0,0,VW,VH], meters_per_unit}`;
  `worldToSvg` exists; scale `s = VW/(xmax-xmin)`.

---

# PHASE A — ENGINE

## Task 1: `library.py` — list + resolve components

**Files:**
- Create: `engine/app/library.py`, `engine/tests/test_library.py`

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_library.py`:
```python
import ezdxf

from app import library


def _make_lib(tmp_path):
    for name in ["EURO 1040 x 1175.dxf", "CHAIR UNIT.dxf"]:
        doc = ezdxf.new("R2010")
        doc.modelspace().add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        doc.saveas(tmp_path / name)
    return str(tmp_path)


def test_list_components(tmp_path):
    d = _make_lib(tmp_path)
    comps = library.list_components(d)
    names = [c["name"] for c in comps]
    assert names == ["CHAIR UNIT", "EURO 1040 x 1175"]  # sorted by name
    assert all(c["id"] for c in comps)
    assert len({c["id"] for c in comps}) == 2  # unique ids


def test_component_path_roundtrip(tmp_path):
    d = _make_lib(tmp_path)
    comps = library.list_components(d)
    cid = comps[0]["id"]
    p = library.component_path(cid, d)
    assert p is not None and p.endswith(".dxf")


def test_component_path_unknown_and_traversal(tmp_path):
    d = _make_lib(tmp_path)
    assert library.component_path("nope", d) is None
    assert library.component_path("../secret", d) is None


def test_list_missing_dir_is_empty():
    assert library.list_components("/no/such/dir") == []
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_library.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.library'`

- [ ] **Step 3: Implement**

`engine/app/library.py`:
```python
import os
import re
from pathlib import Path

LIBRARY_DIR = os.environ.get(
    "CAD_LIBRARY_DIR",
    str(Path.home() / "Downloads" / "BASE_LIBRARY_components"),
)


def _slug(stem: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-").lower() or "component"


def _catalog(directory: str) -> dict[str, str]:
    """Ordered {id: filename} for the .dxf files in directory, ids unique + stable."""
    d = Path(directory)
    if not d.is_dir():
        return {}
    out: dict[str, str] = {}
    for path in sorted(d.glob("*.dxf"), key=lambda p: p.stem.lower()):
        base = _slug(path.stem)
        cid, i = base, 2
        while cid in out:
            cid = f"{base}-{i}"
            i += 1
        out[cid] = path.name
    return out


def list_components(directory: str = LIBRARY_DIR) -> list[dict]:
    return [
        {"id": cid, "name": Path(fn).stem}
        for cid, fn in _catalog(directory).items()
    ]


def component_path(cid: str, directory: str = LIBRARY_DIR) -> str | None:
    fn = _catalog(directory).get(cid)
    if fn is None:
        return None
    return str(Path(directory) / fn)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_library.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/library.py engine/tests/test_library.py
git commit -m "feat(engine): library module lists DXF components from a folder"
```

---

## Task 2: Catalog + cached thumbnail endpoints

**Files:**
- Modify: `engine/app/main.py`, `engine/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_api.py`:
```python
def _lib_dir(tmp_path):
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.modelspace().add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    doc.saveas(tmp_path / "CHAIR UNIT.dxf")
    return str(tmp_path)


def test_library_catalog(tmp_path, monkeypatch):
    from app import library

    monkeypatch.setattr(library, "LIBRARY_DIR", _lib_dir(tmp_path))
    r = client.get("/library")
    assert r.status_code == 200
    comps = r.json()["components"]
    assert any(c["name"] == "CHAIR UNIT" for c in comps)


def test_library_thumbnail_cached(tmp_path, monkeypatch):
    from app import library, main as main_mod

    monkeypatch.setattr(library, "LIBRARY_DIR", _lib_dir(tmp_path))
    main_mod._thumb_cache.clear()
    calls = {"n": 0}
    real = main_mod.render_svg

    def counting(doc):
        calls["n"] += 1
        return real(doc)

    monkeypatch.setattr(main_mod, "render_svg", counting)
    cid = client.get("/library").json()["components"][0]["id"]
    r1 = client.get(f"/library/{cid}/thumbnail.svg")
    r2 = client.get(f"/library/{cid}/thumbnail.svg")
    assert r1.status_code == 200 and "svg" in r1.text[:200].lower()
    assert calls["n"] == 1  # second call served from cache


def test_library_thumbnail_unknown(tmp_path, monkeypatch):
    from app import library

    monkeypatch.setattr(library, "LIBRARY_DIR", _lib_dir(tmp_path))
    assert client.get("/library/nope/thumbnail.svg").status_code == 404
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_api.py -k library -v`
Expected: FAIL (routes 404 / `_thumb_cache` missing)

- [ ] **Step 3: Implement**

In `engine/app/main.py`:

(a) add imports + the cache near the other module state:
```python
from app import components, library, space, tools, units
```
```python
# (path, mtime) -> rendered thumbnail SVG
_thumb_cache: dict[tuple[str, float], str] = {}
```

(b) add the endpoints (after the `/health` route or near the other GETs):
```python
from fastapi.responses import Response  # already imported


@app.get("/library")
def library_catalog() -> dict:
    return {"components": library.list_components()}


@app.get("/library/{cid}/thumbnail.svg")
def library_thumbnail(cid: str):
    path = library.component_path(cid)
    if path is None:
        raise HTTPException(status_code=404, detail="Unknown component")
    key = (path, os.path.getmtime(path))
    svg = _thumb_cache.get(key)
    if svg is None:
        with open(path, "rb") as fh:
            doc = sessions_read(fh.read())
        try:
            svg = render_svg(doc)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"Cannot render component: {e}")
        _thumb_cache[key] = svg
    return Response(content=svg, media_type="image/svg+xml")
```
(c) add a small loader helper next to `_anthropic_client` (reuse recover-mode reader):
```python
def sessions_read(data: bytes):
    from app.sessions import _read_dxf

    return _read_dxf(data)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_api.py -k library -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/main.py engine/tests/test_api.py
git commit -m "feat(engine): library catalog + cached thumbnail endpoints"
```

---

## Task 3: Place-from-library endpoint

**Files:**
- Modify: `engine/app/main.py`, `engine/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_api.py`:
```python
def test_library_place_imports_once_and_centers(sample_bytes, tmp_path, monkeypatch):
    from app import library

    monkeypatch.setattr(library, "LIBRARY_DIR", _lib_dir(tmp_path))
    _fresh_store()
    sid = main.store.create(sample_bytes)
    cid = client.get("/library").json()["components"][0]["id"]

    r = client.post(
        f"/sessions/{sid}/library/place",
        json={"id": cid, "x_m": 5.0, "y_m": 4.0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["change"]["op"] == "place_component"
    assert any(s["handle"] == body["change"]["handle"] for s in body["selectables"])
    assert body["view"] is not None

    # block imported exactly once even if placed again
    n_blocks = len(list(main.store.get(sid).blocks))
    client.post(f"/sessions/{sid}/library/place", json={"id": cid, "x_m": 1, "y_m": 1})
    assert len(list(main.store.get(sid).blocks)) == n_blocks  # no new block def


def test_library_place_unknown_id(sample_bytes, tmp_path, monkeypatch):
    from app import library

    monkeypatch.setattr(library, "LIBRARY_DIR", _lib_dir(tmp_path))
    _fresh_store()
    sid = main.store.create(sample_bytes)
    r = client.post(f"/sessions/{sid}/library/place", json={"id": "ghost", "x_m": 0, "y_m": 0})
    assert r.status_code == 404
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_api.py -k library_place -v`
Expected: FAIL (no route)

- [ ] **Step 3: Implement**

In `engine/app/main.py`, add a request model near `EditRequest`:
```python
class LibraryPlaceRequest(BaseModel):
    id: str
    x_m: float
    y_m: float
    rotation_deg: float = 0.0
    layer: str = "Furniture"
```
Add a per-session map from library id -> imported block name, near `_components`:
```python
# session_id -> {library id: imported block name}
_library_blocks: dict[str, dict[str, str]] = {}
```
Add the endpoint (after the `/edit` route):
```python
@app.post("/sessions/{sid}/library/place")
def library_place(sid: str, req: LibraryPlaceRequest) -> dict:
    doc = store.get(sid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    path = library.component_path(req.id)
    if path is None:
        raise HTTPException(status_code=404, detail="Unknown component")

    imported = _library_blocks.setdefault(sid, {})
    block_name = imported.get(req.id)
    if block_name is None or block_name not in doc.blocks:
        with open(path, "rb") as fh:
            data = fh.read()
        try:
            block_name = components.import_as_block(doc, data, os.path.basename(path))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        imported[req.id] = block_name
        _components.setdefault(sid, []).append(block_name)

    x = units.meters_to_drawing_units(doc, req.x_m)
    y = units.meters_to_drawing_units(doc, req.y_m)
    store.snapshot(sid)
    change = edits.place_component(
        doc, block_name, x, y, rotation_deg=req.rotation_deg, layer=req.layer
    )
    _record_changes(sid, [change])
    current = store.get(sid)
    return {
        "change": change,
        "svg": render_svg(current),
        "view": view_mod.svg_view(current),
        "layers": list_layers(current),
        "selectables": _selectable_entities(current, sid),
    }
```
Add `from app import edits` to the imports if not already present (it is used here).

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/ -q`
Expected: PASS (all engine tests).

- [ ] **Step 5: Commit**

```bash
git add engine/app/main.py engine/tests/test_api.py
git commit -m "feat(engine): place a library component onto the drawing"
```

---

# PHASE B — WEB

## Task 4: `svgToWorldMeters`

**Files:**
- Modify: `web/lib/viewmap.ts`, `web/__tests__/viewmap.test.ts`

- [ ] **Step 1: Write the failing tests**

Append to `web/__tests__/viewmap.test.ts`:
```ts
import { svgToWorldMeters } from "../lib/viewmap";

it("svgToWorldMeters inverts worldToSvg", () => {
  // svg (0, 0) -> world top-left (0, 8) meters; svg (1e6, 8e5) -> (10, 0)
  expect(svgToWorldMeters(view, 0, 0)).toEqual([0, 8]);
  expect(svgToWorldMeters(view, 1_000_000, 800_000)).toEqual([10, 0]);
});

it("svgToWorldMeters honors meters_per_unit (mm)", () => {
  const mm: View = { world: [0, 0, 10000, 8000], viewBox: [0, 0, 1_000_000, 800_000], meters_per_unit: 0.001 };
  // s = 100 svg/unit; svg x=1e6 -> 10000 units -> 10 m
  const [x, y] = svgToWorldMeters(mm, 1_000_000, 0);
  expect(x).toBeCloseTo(10, 6);
  expect(y).toBeCloseTo(8, 6); // svg y=0 -> world top (8000 units -> 8 m)
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- viewmap`
Expected: FAIL (export missing)

- [ ] **Step 3: Implement**

Append to `web/lib/viewmap.ts`:
```ts
export function svgToWorldMeters(view: View, sx: number, sy: number): [number, number] {
  const [xmin, , , ymax] = view.world;
  const s = scale(view);
  const xUnits = xmin + sx / s;
  const yUnits = ymax - sy / s; // Y flip
  return [xUnits * view.meters_per_unit, yUnits * view.meters_per_unit];
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- viewmap`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/viewmap.ts web/__tests__/viewmap.test.ts
git commit -m "feat(web): svgToWorldMeters inverse mapping"
```

---

## Task 5: API client — library

**Files:**
- Modify: `web/lib/api.ts`, `web/__tests__/api.test.ts`

- [ ] **Step 1: Write the failing tests**

Append to `web/__tests__/api.test.ts`:
```ts
it("getLibrary returns the component list", async () => {
  const body = { components: [{ id: "chair", name: "CHAIR UNIT" }] };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const { getLibrary } = await import("../lib/api");
  const res = await getLibrary();
  expect(res.components[0].id).toBe("chair");
});

it("thumbnailUrl builds the right path", async () => {
  const { thumbnailUrl } = await import("../lib/api");
  expect(thumbnailUrl("chair")).toContain("/library/chair/thumbnail.svg");
});

it("placeFromLibrary posts id + coords", async () => {
  const body = { change: { op: "place_component" }, svg: "<svg/>", view: null, layers: [], selectables: [] };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const { placeFromLibrary } = await import("../lib/api");
  const res = await placeFromLibrary("s1", "chair", 5, 4);
  expect(res.change.op).toBe("place_component");
  const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(call[0]).toContain("/sessions/s1/library/place");
  expect(JSON.parse(call[1].body)).toMatchObject({ id: "chair", x_m: 5, y_m: 4 });
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- api`
Expected: FAIL (exports missing)

- [ ] **Step 3: Implement**

In `web/lib/api.ts`, add the type and functions:
```ts
export type LibraryItem = { id: string; name: string };

export async function getLibrary(): Promise<{ components: LibraryItem[] }> {
  return asJson(await fetch(`${BASE}/library`));
}

export function thumbnailUrl(id: string): string {
  return `${BASE}/library/${id}/thumbnail.svg`;
}

export async function placeFromLibrary(
  sid: string,
  id: string,
  x_m: number,
  y_m: number,
  rotation_deg?: number,
  layer?: string,
): Promise<EditResult> {
  return asJson<EditResult>(
    await fetch(`${BASE}/sessions/${sid}/library/place`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, x_m, y_m, rotation_deg, layer }),
    }),
  );
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- api`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/api.ts web/__tests__/api.test.ts
git commit -m "feat(web): library API client (catalog, thumbnail, place)"
```

---

## Task 6: `LibraryPanel`

**Files:**
- Create: `web/components/LibraryPanel.tsx`, `web/__tests__/LibraryPanel.test.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Write the failing tests**

`web/__tests__/LibraryPanel.test.tsx`:
```tsx
import { it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LibraryPanel } from "../components/LibraryPanel";

const items = [
  { id: "euro", name: "EURO 1040 x 1175" },
  { id: "chair", name: "CHAIR UNIT" },
];

it("renders rows for each component", () => {
  render(<LibraryPanel items={items} />);
  expect(screen.getByText("EURO 1040 x 1175")).toBeTruthy();
  expect(screen.getByText("CHAIR UNIT")).toBeTruthy();
});

it("filters by search text", async () => {
  render(<LibraryPanel items={items} />);
  await userEvent.type(screen.getByPlaceholderText(/search/i), "chair");
  expect(screen.queryByText("EURO 1040 x 1175")).toBeNull();
  expect(screen.getByText("CHAIR UNIT")).toBeTruthy();
});

it("sets the component id on drag start", () => {
  render(<LibraryPanel items={items} />);
  const row = screen.getByTestId("lib-euro");
  const setData = vi.fn();
  fireEvent.dragStart(row, { dataTransfer: { setData } });
  expect(setData).toHaveBeenCalledWith("application/x-cad-component", "euro");
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- LibraryPanel`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement**

`web/components/LibraryPanel.tsx`:
```tsx
"use client";
import { useState } from "react";
import { thumbnailUrl, type LibraryItem } from "../lib/api";

export function LibraryPanel({ items }: { items: LibraryItem[] }) {
  const [q, setQ] = useState("");
  const filtered = items.filter((it) =>
    it.name.toLowerCase().includes(q.trim().toLowerCase()),
  );
  return (
    <div className="library">
      <div className="panel-head">Components</div>
      <input
        className="library-search"
        placeholder="Search components…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="library-list">
        {filtered.map((it) => (
          <div
            key={it.id}
            data-testid={`lib-${it.id}`}
            className="library-item"
            draggable
            onDragStart={(e) =>
              e.dataTransfer.setData("application/x-cad-component", it.id)
            }
            title={it.name}
          >
            <img
              className="library-thumb"
              src={thumbnailUrl(it.id)}
              alt=""
              loading="lazy"
              draggable={false}
            />
            <span className="library-name">{it.name}</span>
          </div>
        ))}
        {filtered.length === 0 && <div className="library-empty">No matches</div>}
      </div>
    </div>
  );
}
```
Add to `web/app/globals.css`:
```css
.library {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--line);
  background: var(--panel);
  width: 240px;
}
.library-search {
  margin: 8px 12px;
  padding: 7px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-sm);
  background: var(--panel-2);
  color: var(--ink);
  font-size: 13px;
}
.library-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  align-content: start;
}
.library-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 6px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--panel-2);
  cursor: grab;
}
.library-item:hover {
  border-color: var(--accent);
}
.library-thumb {
  width: 100%;
  height: 64px;
  object-fit: contain;
  background: #fff;
  border-radius: 4px;
  pointer-events: none;
}
.library-name {
  font-size: 10.5px;
  line-height: 1.2;
  text-align: center;
  color: var(--ink-soft);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.library-empty {
  grid-column: 1 / -1;
  padding: 16px;
  text-align: center;
  color: var(--ink-soft);
  font-size: 12.5px;
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- LibraryPanel`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/components/LibraryPanel.tsx web/__tests__/LibraryPanel.test.tsx web/app/globals.css
git commit -m "feat(web): searchable, draggable LibraryPanel with thumbnails"
```

---

## Task 7: Canvas accepts a component drop

**Files:**
- Modify: `web/components/SvgViewer.tsx`, `web/__tests__/SvgViewer.test.tsx`

- [ ] **Step 1: Write the failing test**

Append to `web/__tests__/SvgViewer.test.tsx`:
```tsx
it("dropping a component calls onDropComponent with world meters", () => {
  const onDropComponent = vi.fn();
  render(
    <SvgViewer svg="<svg/>" view={view} selectables={[]} onDropComponent={onDropComponent} />,
  );
  const stage = document.querySelector(".canvas-stage") as HTMLElement;
  const getData = vi.fn().mockReturnValue("euro");
  // identity-CTM shim (from beforeEach) makes svg coords == client coords.
  fireEvent.drop(stage, { clientX: 1_000_000, clientY: 800_000, dataTransfer: { getData } });
  expect(getData).toHaveBeenCalledWith("application/x-cad-component");
  // svg (1e6, 8e5) -> world (10, 0) meters in the 10x8 view
  expect(onDropComponent).toHaveBeenCalledWith("euro", 10, 0);
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- SvgViewer`
Expected: FAIL (no drop handling / prop)

- [ ] **Step 3: Implement**

In `web/components/SvgViewer.tsx`:

(a) add to `Props`:
```tsx
  onDropComponent?: (id: string, x_m: number, y_m: number) => void;
```
(b) destructure it in the function signature (add `onDropComponent`).
(c) import `svgToWorldMeters`:
```tsx
import { svgRectFromBBox, svgDeltaToMeters, svgToWorldMeters, type View } from "../lib/viewmap";
```
(d) add a helper to map an absolute client point to svg coords (reuses the overlay CTM):
```tsx
  function clientToSvgPoint(clientX: number, clientY: number): { x: number; y: number } | null {
    const svgEl = overlayRef.current;
    if (!svgEl) return null;
    const pt = svgEl.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svgEl.getScreenCTM();
    const local = ctm ? pt.matrixTransform(ctm.inverse()) : pt;
    return { x: local.x, y: local.y };
  }
```
(e) on the `.canvas-stage` div, add drag handlers:
```tsx
        onDragOver={(e) => {
          if (onDropComponent) e.preventDefault();
        }}
        onDrop={(e) => {
          if (!onDropComponent || !view) return;
          const id = e.dataTransfer.getData("application/x-cad-component");
          if (!id) return;
          e.preventDefault();
          const p = clientToSvgPoint(e.clientX, e.clientY);
          if (!p) return;
          const [x_m, y_m] = svgToWorldMeters(view, p.x, p.y);
          onDropComponent(id, x_m, y_m);
        }}
```
Note: `clientToSvgPoint` needs `overlayRef`, which only exists when `view` is set (the
overlay renders). The drop handler already guards on `view`.

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- SvgViewer`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/components/SvgViewer.tsx web/__tests__/SvgViewer.test.tsx
git commit -m "feat(web): drop a library component onto the canvas"
```

---

## Task 8: Wire the left panel + drop into the page

**Files:**
- Modify: `web/app/page.tsx`, `web/app/globals.css`

- [ ] **Step 1: Implement page wiring**

In `web/app/page.tsx`:

(a) imports + state:
```tsx
import { LibraryPanel } from "../components/LibraryPanel";
import {
  /* existing… */ getLibrary, placeFromLibrary, type LibraryItem,
} from "../lib/api";
```
```tsx
  const [libraryItems, setLibraryItems] = useState<LibraryItem[]>([]);
```
(b) load the library once on mount:
```tsx
  useEffect(() => {
    getLibrary()
      .then((r) => setLibraryItems(r.components))
      .catch(() => {});
  }, []);
```
(add `import { useEffect, useState } from "react";`).

(c) the drop handler (reuses the EditResult update like `handleEdit`):
```tsx
  async function handleDropComponent(id: string, x_m: number, y_m: number) {
    if (!sid) return;
    try {
      const res = await placeFromLibrary(sid, id, x_m, y_m);
      setSvg(res.svg);
      setView(res.view);
      setLayers(res.layers);
      setSelectables(res.selectables);
      setChanges((c) => [...c, res.change]);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  }
```
(d) put the panel as the left column of `.workspace` and pass the drop handler to the viewer:
```tsx
      <div className="workspace">
        <LibraryPanel items={libraryItems} />
        <div className="canvas-wrap">
          <SvgViewer
            svg={svg}
            view={view}
            selectables={selectables}
            selected={selected}
            onSelect={setSelected}
            onEdit={handleEdit}
            onDropComponent={handleDropComponent}
          />
        </div>
        <aside className="sidebar">
          {/* unchanged */}
        </aside>
      </div>
```

(e) ensure the workspace lays out three columns. In `web/app/globals.css`, find the
`.workspace` rule and set its grid to include the left panel (if it uses `grid-template-columns`,
prepend `auto`; if it uses flex, the panel's fixed `width:240px` already slots in). Add a
safe override at the end of the file:
```css
.workspace {
  display: flex;
  min-height: 0;
}
.canvas-wrap {
  flex: 1;
  min-width: 0;
}
```

- [ ] **Step 2: Verify build + all web tests**

Run: `cd web && npm test && npm run build`
Expected: PASS, build succeeds.

- [ ] **Step 3: Commit**

```bash
git add web/app/page.tsx web/app/globals.css
git commit -m "feat(web): mount the component library panel and wire drop-to-place"
```

---

## Task 9: Manual end-to-end verification

**Files:** none (manual).

- [ ] **Step 1: Restart engine (so it serves the library) + open the app**

```bash
lsof -ti :8000 | xargs kill 2>/dev/null
cd engine && .venv/bin/uvicorn app.main:app --reload --port 8000 > /tmp/cad-engine.log 2>&1 &
# web already runs on :3000
```
Confirm `curl -s localhost:8000/library | head -c 200` lists components.

- [ ] **Step 2: Use it**

Open http://localhost:3000, upload BASE CAD (set units to mm). The left panel shows
thumbnails; type "euro" to filter. Drag `EURO 1040 x 1175` onto the canvas near the center;
confirm it appears at the drop point, correctly sized, on a Furniture layer, and is
selectable (drag/rotate/delete) and Undo-able.

- [ ] **Step 3: Note results.** No commit (manual step).

---

## Self-Review notes (addressed)

- **Spec coverage:** folder listing + env (T1); catalog + cached thumbnail (T2); place-from-
  library lazy import + center placement (T3); `svgToWorldMeters` (T4); clients (T5); searchable
  draggable panel with thumbnails (T6); canvas drop → world meters (T7); left column + wiring,
  load-on-mount, drop handler (T8); manual E2E (T9). Error handling: unknown id 404 (T2/T3),
  empty geometry 422 (T3), empty dir → empty list (T1), drop with no drawing no-ops (T7),
  Undo via snapshot (T3). All covered.
- **No placeholders:** every step has concrete code/commands.
- **Type consistency:** `LibraryItem {id,name}` consistent engine↔`api.ts`↔`LibraryPanel`;
  `placeFromLibrary(...)` ↔ `LibraryPlaceRequest{id,x_m,y_m,rotation_deg,layer}` ↔
  `/sessions/{id}/library/place`; drop dataTransfer key `"application/x-cad-component"`
  identical in `LibraryPanel` (set) and `SvgViewer` (get); `placeFromLibrary` returns the
  shared `EditResult` so `page.tsx` reuses the `handleEdit` update shape; `svgToWorldMeters`
  mirrors `worldToSvg` (drawing units) then ×`meters_per_unit`.
- **Known risks:** (1) the default `CAD_LIBRARY_DIR` is the user's Downloads path — overridable
  via env; engine returns an empty catalog if absent (no crash). (2) Thumbnail SVGs are the
  full render (no downscering); the panel constrains size via CSS `object-fit` — acceptable for
  small fixtures, revisit only if payloads are large. (3) `.workspace` may already define grid
  columns; T8 step (e) adds an explicit flex override at end-of-file to guarantee the 3-column
  layout — eyeball in T9.
```
