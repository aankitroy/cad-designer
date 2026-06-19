# cad-designer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local web app to upload a 2D DXF floor plan, view it rendered as SVG, and edit it through natural-language chat that drives structured `ezdxf` edits with live re-render, undo, and download.

**Architecture:** Python FastAPI engine owns all CAD logic (`ezdxf`) and the Claude tool-use loop (`anthropic` SDK), holding sessions in memory. A Next.js (App Router, TS) frontend is pure presentation + chat, talking to the engine over HTTP. Build the engine first (testable on its own), then the web UI.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, ezdxf, anthropic, pytest, httpx; Next.js, TypeScript, Vitest, React Testing Library.

---

## File Structure

```
cad-designer/
├── engine/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app + routes
│   │   ├── sessions.py        # in-memory session store + snapshots/undo
│   │   ├── render.py          # ezdxf doc -> SVG
│   │   ├── units.py           # $INSUNITS -> drawing-unit conversion
│   │   ├── edits.py           # entity edit ops (move/delete/add_*) returning Change records
│   │   ├── query.py           # list_layers / query_entities
│   │   ├── tools.py           # Claude tool schemas + dispatch -> edits/query
│   │   └── agent.py           # Claude tool-use loop
│   └── tests/
│       ├── conftest.py        # fixture DXF builder
│       ├── test_render.py
│       ├── test_query.py
│       ├── test_edits.py
│       ├── test_units.py
│       ├── test_tools.py
│       ├── test_agent.py
│       └── test_api.py
└── web/
    ├── package.json
    ├── next.config.ts
    ├── vitest.config.ts
    ├── src/
    │   ├── lib/api.ts         # typed engine client
    │   ├── app/page.tsx       # main screen layout
    │   └── components/
    │       ├── Uploader.tsx
    │       ├── SvgViewer.tsx  # pan/zoom container
    │       ├── ChatPanel.tsx
    │       └── ChangeLog.tsx
    └── src/__tests__/
        ├── Uploader.test.tsx
        ├── ChatPanel.test.tsx
        └── api.test.ts
```

---

# PHASE A — ENGINE

## Task 1: Scaffold the engine

**Files:**
- Create: `engine/pyproject.toml`, `engine/app/__init__.py`, `engine/app/main.py`, `engine/tests/__init__.py`

- [ ] **Step 1: Create venv and project metadata**

Run from `cad-designer/engine`:
```bash
cd engine
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install "fastapi>=0.110" "uvicorn[standard]>=0.27" "ezdxf>=1.3" "anthropic>=0.40" "python-multipart>=0.0.9" "pytest>=8" "httpx>=0.27"
.venv/bin/pip freeze > requirements.txt
```

`pyproject.toml`:
```toml
[project]
name = "cad-designer-engine"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 2: Minimal app + health route**

`app/__init__.py`: (empty file)

`app/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="cad-designer engine")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

`tests/__init__.py`: (empty file)

- [ ] **Step 3: Write health test**

`engine/tests/test_api.py`:
```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 4: Run test**

Run: `cd engine && .venv/bin/pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/ && git commit -m "feat(engine): scaffold FastAPI app with health route"
```

---

## Task 2: Fixture DXF builder

**Files:**
- Create: `engine/tests/conftest.py`

- [ ] **Step 1: Write the fixture**

A reusable in-memory DXF with known entities so every test has predictable handles/layers.

`engine/tests/conftest.py`:
```python
import ezdxf
import pytest


@pytest.fixture
def sample_doc():
    """A small floor plan: one wall, a fixture block insert, a text label."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6  # meters
    msp = doc.modelspace()

    # walls layer
    doc.layers.add("WALLS", color=1)
    doc.layers.add("FIXTURES", color=3)
    doc.layers.add("TEXT", color=7)

    wall = msp.add_lwpolyline(
        [(0, 0), (10, 0), (10, 8), (0, 8), (0, 0)], dxfattribs={"layer": "WALLS"}
    )
    label = msp.add_text(
        "CASH COUNTER", dxfattribs={"layer": "TEXT", "height": 0.3}
    )
    label.set_placement((2, 2))
    line = msp.add_line((2, 2), (4, 2), dxfattribs={"layer": "FIXTURES"})

    return {
        "doc": doc,
        "wall_handle": wall.dxf.handle,
        "label_handle": label.dxf.handle,
        "line_handle": line.dxf.handle,
    }


@pytest.fixture
def sample_bytes(sample_doc):
    """The sample doc serialized to DXF bytes (for upload tests)."""
    import io

    buf = io.StringIO()
    sample_doc["doc"].write(buf)
    return buf.getvalue().encode("utf-8")
```

- [ ] **Step 2: Verify fixture imports cleanly**

Run: `cd engine && .venv/bin/pytest tests/ -v`
Expected: PASS (existing health test still passes; no new tests yet)

- [ ] **Step 3: Commit**

```bash
git add engine/tests/conftest.py && git commit -m "test(engine): add sample DXF fixtures"
```

---

## Task 3: Render DXF to SVG

**Files:**
- Create: `engine/app/render.py`, `engine/tests/test_render.py`

- [ ] **Step 1: Write the failing test**

`engine/tests/test_render.py`:
```python
from app.render import render_svg


def test_render_returns_svg_string(sample_doc):
    svg = render_svg(sample_doc["doc"])
    assert isinstance(svg, str)
    assert svg.lstrip().startswith("<")
    assert "svg" in svg[:200].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd engine && .venv/bin/pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: app.render`

- [ ] **Step 3: Implement render**

`engine/app/render.py`:
```python
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.svg import SVGBackend
from ezdxf.addons.drawing.layout import Page
from ezdxf.document import Drawing


def render_svg(doc: Drawing) -> str:
    """Render modelspace to a standalone SVG string."""
    msp = doc.modelspace()
    backend = SVGBackend()
    Frontend(RenderContext(doc), backend).draw_layout(msp)
    page = Page(0, 0)  # auto-size from content bounding box
    return backend.get_string(page)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd engine && .venv/bin/pytest tests/test_render.py -v`
Expected: PASS. If `get_string` signature differs in the installed ezdxf, run `.venv/bin/python -c "from ezdxf.addons.drawing.svg import SVGBackend; help(SVGBackend.get_string)"` and adjust to the available API (older versions: `backend.get_string(page)` vs newer `backend.get_string()`).

- [ ] **Step 5: Commit**

```bash
git add engine/app/render.py engine/tests/test_render.py && git commit -m "feat(engine): render DXF modelspace to SVG"
```

---

## Task 4: Query — list_layers and query_entities

**Files:**
- Create: `engine/app/query.py`, `engine/tests/test_query.py`

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_query.py`:
```python
from app.query import list_layers, query_entities


def test_list_layers(sample_doc):
    layers = list_layers(sample_doc["doc"])
    names = {l["name"] for l in layers}
    assert {"WALLS", "FIXTURES", "TEXT"} <= names


def test_query_by_layer(sample_doc):
    results = query_entities(sample_doc["doc"], layer="WALLS")
    assert any(e["handle"] == sample_doc["wall_handle"] for e in results)
    assert all(e["layer"] == "WALLS" for e in results)


def test_query_by_near_text(sample_doc):
    results = query_entities(sample_doc["doc"], near_text="cash")
    assert any("CASH" in (e.get("text") or "").upper() for e in results)


def test_query_returns_handles_and_types(sample_doc):
    results = query_entities(sample_doc["doc"])
    sample = results[0]
    assert "handle" in sample and "type" in sample and "layer" in sample
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_query.py -v`
Expected: FAIL with `ModuleNotFoundError: app.query`

- [ ] **Step 3: Implement query**

`engine/app/query.py`:
```python
from ezdxf.document import Drawing


def list_layers(doc: Drawing) -> list[dict]:
    msp = doc.modelspace()
    counts: dict[str, int] = {}
    for e in msp:
        counts[e.dxf.layer] = counts.get(e.dxf.layer, 0) + 1
    return [
        {"name": layer.dxf.name, "entity_count": counts.get(layer.dxf.name, 0)}
        for layer in doc.layers
    ]


def _entity_text(e) -> str | None:
    if e.dxftype() in ("TEXT", "MTEXT"):
        return e.dxf.text if e.dxftype() == "TEXT" else e.text
    return None


def _entity_point(e):
    try:
        if e.dxftype() == "LINE":
            return (e.dxf.start.x, e.dxf.start.y)
        if e.dxftype() in ("TEXT", "INSERT", "CIRCLE"):
            p = e.dxf.insert if e.dxftype() != "CIRCLE" else e.dxf.center
            return (p.x, p.y)
        if e.dxftype() == "LWPOLYLINE":
            pts = list(e.get_points())
            return (pts[0][0], pts[0][1]) if pts else None
    except Exception:
        return None
    return None


def query_entities(
    doc: Drawing,
    layer: str | None = None,
    type: str | None = None,
    near_text: str | None = None,
    near_point: tuple[float, float] | None = None,
    radius: float | None = None,
) -> list[dict]:
    msp = doc.modelspace()
    out: list[dict] = []
    for e in msp:
        if layer and e.dxf.layer != layer:
            continue
        if type and e.dxftype() != type.upper():
            continue
        text = _entity_text(e)
        if near_text and (text is None or near_text.lower() not in text.lower()):
            continue
        pt = _entity_point(e)
        if near_point and radius is not None and pt is not None:
            dx, dy = pt[0] - near_point[0], pt[1] - near_point[1]
            if (dx * dx + dy * dy) ** 0.5 > radius:
                continue
        out.append(
            {
                "handle": e.dxf.handle,
                "type": e.dxftype(),
                "layer": e.dxf.layer,
                "text": text,
                "point": pt,
            }
        )
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_query.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/query.py engine/tests/test_query.py && git commit -m "feat(engine): list_layers and query_entities"
```

---

## Task 5: Unit conversion

**Files:**
- Create: `engine/app/units.py`, `engine/tests/test_units.py`

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_units.py`:
```python
from app.units import meters_to_drawing_units


def test_meters_when_doc_in_meters(sample_doc):
    # $INSUNITS == 6 (meters): 2m -> 2.0 drawing units
    assert meters_to_drawing_units(sample_doc["doc"], 2.0) == 2.0


def test_meters_when_doc_in_millimeters():
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # millimeters
    assert meters_to_drawing_units(doc, 2.0) == 2000.0


def test_meters_when_units_unset():
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 0  # unitless -> assume drawing units == meters
    assert meters_to_drawing_units(doc, 2.0) == 2.0
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_units.py -v`
Expected: FAIL with `ModuleNotFoundError: app.units`

- [ ] **Step 3: Implement units**

`engine/app/units.py`:
```python
from ezdxf.document import Drawing

# $INSUNITS code -> meters per drawing unit
_METERS_PER_UNIT = {
    0: 1.0,      # unitless: assume meters
    1: 0.0254,   # inches
    2: 0.3048,   # feet
    4: 0.001,    # millimeters
    5: 0.01,     # centimeters
    6: 1.0,      # meters
}


def meters_to_drawing_units(doc: Drawing, meters: float) -> float:
    code = int(doc.header.get("$INSUNITS", 0))
    mpu = _METERS_PER_UNIT.get(code, 1.0)
    return meters / mpu
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_units.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/units.py engine/tests/test_units.py && git commit -m "feat(engine): meters->drawing-unit conversion from \$INSUNITS"
```

---

## Task 6: Edit operations

**Files:**
- Create: `engine/app/edits.py`, `engine/tests/test_edits.py`

Each op returns a `Change` dict: `{"op", "handle", "before", "after", "summary"}`. Ops mutate the passed `doc`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_edits.py`:
```python
import pytest
from app import edits


def test_move_entity(sample_doc):
    doc = sample_doc["doc"]
    h = sample_doc["line_handle"]
    change = edits.move_entity(doc, h, dx=1.0, dy=2.0)
    assert change["op"] == "move_entity"
    assert change["handle"] == h
    line = doc.entitydb[h]
    assert line.dxf.start.x == pytest.approx(3.0)  # was (2,2)
    assert line.dxf.start.y == pytest.approx(4.0)


def test_delete_entity(sample_doc):
    doc = sample_doc["doc"]
    h = sample_doc["line_handle"]
    change = edits.delete_entity(doc, h)
    assert change["op"] == "delete_entity"
    assert h not in doc.entitydb or doc.entitydb[h].is_alive is False


def test_add_text_label(sample_doc):
    doc = sample_doc["doc"]
    change = edits.add_text_label(doc, x=5, y=5, text="FITTING ROOM", layer="TEXT")
    assert change["op"] == "add_text_label"
    new = doc.entitydb[change["handle"]]
    assert new.dxf.text == "FITTING ROOM"
    assert new.dxf.layer == "TEXT"


def test_add_wall(sample_doc):
    doc = sample_doc["doc"]
    change = edits.add_wall(doc, x1=0, y1=0, x2=5, y2=0, layer="WALLS")
    assert change["op"] == "add_wall"
    new = doc.entitydb[change["handle"]]
    assert new.dxftype() == "LWPOLYLINE"
    assert new.dxf.layer == "WALLS"


def test_set_layer(sample_doc):
    doc = sample_doc["doc"]
    h = sample_doc["line_handle"]
    change = edits.set_layer(doc, h, "WALLS")
    assert doc.entitydb[h].dxf.layer == "WALLS"
    assert change["before"] == "FIXTURES"


def test_move_missing_handle_raises(sample_doc):
    with pytest.raises(edits.EntityNotFound):
        edits.move_entity(sample_doc["doc"], "DEADBEEF", dx=1, dy=1)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_edits.py -v`
Expected: FAIL with `ModuleNotFoundError: app.edits`

- [ ] **Step 3: Implement edits**

`engine/app/edits.py`:
```python
from ezdxf.document import Drawing


class EntityNotFound(Exception):
    pass


def _get(doc: Drawing, handle: str):
    e = doc.entitydb.get(handle)
    if e is None or not e.is_alive:
        raise EntityNotFound(f"No entity with handle {handle}")
    return e


def move_entity(doc: Drawing, handle: str, dx: float, dy: float) -> dict:
    e = _get(doc, handle)
    before = _summarize_point(e)
    e.translate(dx, dy, 0)
    return {
        "op": "move_entity",
        "handle": handle,
        "before": before,
        "after": _summarize_point(e),
        "summary": f"Moved {e.dxftype()} by ({dx}, {dy})",
    }


def delete_entity(doc: Drawing, handle: str) -> dict:
    e = _get(doc, handle)
    etype = e.dxftype()
    doc.modelspace().delete_entity(e)
    return {
        "op": "delete_entity",
        "handle": handle,
        "before": etype,
        "after": None,
        "summary": f"Deleted {etype}",
    }


def add_text_label(doc: Drawing, x: float, y: float, text: str,
                   layer: str = "TEXT", height: float = 0.3) -> dict:
    msp = doc.modelspace()
    t = msp.add_text(text, dxfattribs={"layer": layer, "height": height})
    t.set_placement((x, y))
    return {
        "op": "add_text_label",
        "handle": t.dxf.handle,
        "before": None,
        "after": text,
        "summary": f"Added label '{text}' at ({x}, {y})",
    }


def add_wall(doc: Drawing, x1: float, y1: float, x2: float, y2: float,
             layer: str = "WALLS") -> dict:
    msp = doc.modelspace()
    p = msp.add_lwpolyline([(x1, y1), (x2, y2)], dxfattribs={"layer": layer})
    return {
        "op": "add_wall",
        "handle": p.dxf.handle,
        "before": None,
        "after": [(x1, y1), (x2, y2)],
        "summary": f"Added wall ({x1},{y1})->({x2},{y2})",
    }


def set_layer(doc: Drawing, handle: str, layer: str) -> dict:
    e = _get(doc, handle)
    before = e.dxf.layer
    e.dxf.layer = layer
    return {
        "op": "set_layer",
        "handle": handle,
        "before": before,
        "after": layer,
        "summary": f"Moved {e.dxftype()} to layer {layer}",
    }


def _summarize_point(e):
    try:
        if e.dxftype() == "LINE":
            return [e.dxf.start.x, e.dxf.start.y]
        if e.dxftype() in ("TEXT", "INSERT"):
            return [e.dxf.insert.x, e.dxf.insert.y]
        if e.dxftype() == "CIRCLE":
            return [e.dxf.center.x, e.dxf.center.y]
    except Exception:
        return None
    return None
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_edits.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/edits.py engine/tests/test_edits.py && git commit -m "feat(engine): entity edit operations with Change records"
```

---

## Task 7: Tool schemas and dispatch

**Files:**
- Create: `engine/app/tools.py`, `engine/tests/test_tools.py`

Maps Claude tool calls (name + args) to `query`/`edits` functions against a doc, with meter→unit conversion applied to distance args.

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_tools.py`:
```python
from app.tools import TOOL_SCHEMAS, dispatch


def test_schemas_have_required_shape():
    names = {t["name"] for t in TOOL_SCHEMAS}
    assert {"query_entities", "move_entity", "add_text_label",
            "add_wall", "delete_entity", "set_layer", "list_layers"} <= names
    for t in TOOL_SCHEMAS:
        assert "name" in t and "description" in t and "input_schema" in t


def test_dispatch_query(sample_doc):
    result = dispatch(sample_doc["doc"], "query_entities", {"layer": "WALLS"})
    assert isinstance(result["result"], list)
    assert result["change"] is None


def test_dispatch_move_converts_meters(sample_doc):
    # doc is in meters, so dx_m=2 -> 2 drawing units
    h = sample_doc["line_handle"]
    out = dispatch(sample_doc["doc"], "move_entity",
                   {"handle": h, "dx_m": 2.0, "dy_m": 0.0})
    assert out["change"]["op"] == "move_entity"
    line = sample_doc["doc"].entitydb[h]
    assert abs(line.dxf.start.x - 4.0) < 1e-6  # was 2.0


def test_dispatch_unknown_tool(sample_doc):
    out = dispatch(sample_doc["doc"], "frobnicate", {})
    assert out["error"]
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: app.tools`

- [ ] **Step 3: Implement tools**

`engine/app/tools.py`:
```python
from ezdxf.document import Drawing
from app import edits, query, units

TOOL_SCHEMAS = [
    {
        "name": "list_layers",
        "description": "List all layers with entity counts.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "query_entities",
        "description": "Find entities by layer, type, nearby text, or proximity. "
                       "Use this to resolve vague references like 'the cash counter' "
                       "into concrete entity handles before editing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "layer": {"type": "string"},
                "type": {"type": "string", "description": "DXF type e.g. LINE, TEXT, LWPOLYLINE"},
                "near_text": {"type": "string"},
            },
        },
    },
    {
        "name": "move_entity",
        "description": "Move an entity by a delta in meters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "dx_m": {"type": "number", "description": "delta X in meters"},
                "dy_m": {"type": "number", "description": "delta Y in meters"},
            },
            "required": ["handle", "dx_m", "dy_m"],
        },
    },
    {
        "name": "add_text_label",
        "description": "Add a text label at a point (meters from origin).",
        "input_schema": {
            "type": "object",
            "properties": {
                "x_m": {"type": "number"},
                "y_m": {"type": "number"},
                "text": {"type": "string"},
                "layer": {"type": "string"},
            },
            "required": ["x_m", "y_m", "text"],
        },
    },
    {
        "name": "add_wall",
        "description": "Add a straight wall between two points (meters).",
        "input_schema": {
            "type": "object",
            "properties": {
                "x1_m": {"type": "number"}, "y1_m": {"type": "number"},
                "x2_m": {"type": "number"}, "y2_m": {"type": "number"},
                "layer": {"type": "string"},
            },
            "required": ["x1_m", "y1_m", "x2_m", "y2_m"],
        },
    },
    {
        "name": "delete_entity",
        "description": "Delete an entity by handle.",
        "input_schema": {
            "type": "object",
            "properties": {"handle": {"type": "string"}},
            "required": ["handle"],
        },
    },
    {
        "name": "set_layer",
        "description": "Move an entity to a different layer.",
        "input_schema": {
            "type": "object",
            "properties": {"handle": {"type": "string"}, "layer": {"type": "string"}},
            "required": ["handle", "layer"],
        },
    },
]


def dispatch(doc: Drawing, name: str, args: dict) -> dict:
    """Returns {result, change, error}. result for reads, change for writes."""
    try:
        m = lambda v: units.meters_to_drawing_units(doc, float(v))
        if name == "list_layers":
            return {"result": query.list_layers(doc), "change": None, "error": None}
        if name == "query_entities":
            return {"result": query.query_entities(
                doc, layer=args.get("layer"), type=args.get("type"),
                near_text=args.get("near_text")), "change": None, "error": None}
        if name == "move_entity":
            c = edits.move_entity(doc, args["handle"], m(args["dx_m"]), m(args["dy_m"]))
            return {"result": None, "change": c, "error": None}
        if name == "add_text_label":
            c = edits.add_text_label(doc, m(args["x_m"]), m(args["y_m"]),
                                     args["text"], layer=args.get("layer", "TEXT"))
            return {"result": None, "change": c, "error": None}
        if name == "add_wall":
            c = edits.add_wall(doc, m(args["x1_m"]), m(args["y1_m"]),
                               m(args["x2_m"]), m(args["y2_m"]),
                               layer=args.get("layer", "WALLS"))
            return {"result": None, "change": c, "error": None}
        if name == "delete_entity":
            return {"result": None, "change": edits.delete_entity(doc, args["handle"]), "error": None}
        if name == "set_layer":
            return {"result": None, "change": edits.set_layer(doc, args["handle"], args["layer"]), "error": None}
        return {"result": None, "change": None, "error": f"Unknown tool {name}"}
    except edits.EntityNotFound as e:
        return {"result": None, "change": None, "error": str(e)}
    except (KeyError, ValueError) as e:
        return {"result": None, "change": None, "error": f"Bad args for {name}: {e}"}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/tools.py engine/tests/test_tools.py && git commit -m "feat(engine): Claude tool schemas and dispatch with unit conversion"
```

---

## Task 8: Claude tool-use loop (mocked in tests)

**Files:**
- Create: `engine/app/agent.py`, `engine/tests/test_agent.py`

The loop accepts a doc + user message, calls Claude with `TOOL_SCHEMAS`, executes any tool calls via `dispatch`, feeds results back, and repeats until Claude stops. Collects all `change` records. The Anthropic client is injected so tests can mock it.

- [ ] **Step 1: Write the failing test**

`engine/tests/test_agent.py`:
```python
from app.agent import run_agent


class FakeBlock:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class FakeMessages:
    def __init__(self, scripted):
        self._scripted = list(scripted)

    def create(self, **kwargs):
        return self._scripted.pop(0)


class FakeClient:
    def __init__(self, scripted):
        self.messages = FakeMessages(scripted)


def test_agent_executes_tool_then_finishes(sample_doc):
    h = sample_doc["line_handle"]
    scripted = [
        FakeResponse("tool_use", [
            FakeBlock(type="text", text="Moving it."),
            FakeBlock(type="tool_use", id="t1", name="move_entity",
                      input={"handle": h, "dx_m": -2.0, "dy_m": 0.0}),
        ]),
        FakeResponse("end_turn", [FakeBlock(type="text", text="Done — moved 2m left.")]),
    ]
    out = run_agent(
        client=FakeClient(scripted),
        doc=sample_doc["doc"],
        user_message="move the fixture 2m left",
        model="claude-sonnet-4-6",
    )
    assert out["reply"] == "Done — moved 2m left."
    assert len(out["changes"]) == 1
    assert out["changes"][0]["op"] == "move_entity"
    line = sample_doc["doc"].entitydb[h]
    assert abs(line.dxf.start.x - 0.0) < 1e-6  # was 2.0, moved -2
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: app.agent`

- [ ] **Step 3: Implement agent**

`engine/app/agent.py`:
```python
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
    return " ".join(b.text for b in content if getattr(b, "type", None) == "text").strip()


def run_agent(client, doc: Drawing, user_message: str,
              model: str = "claude-sonnet-4-6") -> dict:
    messages = [{"role": "user", "content": user_message}]
    changes: list[dict] = []
    reply = ""

    for _ in range(MAX_TURNS):
        resp = client.messages.create(
            model=model, max_tokens=2048, system=SYSTEM,
            tools=TOOL_SCHEMAS, messages=messages,
        )
        reply = _text_from(resp.content) or reply
        if resp.stop_reason != "tool_use":
            break

        # echo assistant turn back into history
        messages.append({"role": "assistant", "content": [
            _block_to_dict(b) for b in resp.content
        ]})

        tool_results = []
        for b in resp.content:
            if getattr(b, "type", None) != "tool_use":
                continue
            out = dispatch(doc, b.name, b.input)
            if out["change"]:
                changes.append(out["change"])
            payload = out["error"] or out["change"] or out["result"]
            tool_results.append({
                "type": "tool_result", "tool_use_id": b.id,
                "content": str(payload),
                "is_error": bool(out["error"]),
            })
        messages.append({"role": "user", "content": tool_results})

    return {"reply": reply, "changes": changes}


def _block_to_dict(b) -> dict:
    t = getattr(b, "type", None)
    if t == "text":
        return {"type": "text", "text": b.text}
    if t == "tool_use":
        return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
    return {"type": "text", "text": ""}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/agent.py engine/tests/test_agent.py && git commit -m "feat(engine): Claude tool-use loop with injected client"
```

---

## Task 9: Session store with undo

**Files:**
- Create: `engine/app/sessions.py`, `engine/tests/test_sessions.py`

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_sessions.py`:
```python
import pytest
from app.sessions import SessionStore
from app import edits


def test_create_and_get(sample_bytes):
    store = SessionStore()
    sid = store.create(sample_bytes)
    assert store.get(sid) is not None


def test_create_rejects_bad_dxf():
    store = SessionStore()
    with pytest.raises(ValueError):
        store.create(b"this is not a dxf")


def test_snapshot_and_undo(sample_bytes):
    store = SessionStore()
    sid = store.create(sample_bytes)
    doc = store.get(sid)
    handles_before = len(list(doc.modelspace()))

    store.snapshot(sid)
    edits.add_wall(store.get(sid), 0, 0, 1, 1)
    assert len(list(store.get(sid).modelspace())) == handles_before + 1

    store.undo(sid)
    assert len(list(store.get(sid).modelspace())) == handles_before


def test_undo_with_no_history_is_noop(sample_bytes):
    store = SessionStore()
    sid = store.create(sample_bytes)
    store.undo(sid)  # should not raise
    assert store.get(sid) is not None
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_sessions.py -v`
Expected: FAIL with `ModuleNotFoundError: app.sessions`

- [ ] **Step 3: Implement sessions**

`engine/app/sessions.py`:
```python
import io
import uuid

import ezdxf
from ezdxf.document import Drawing


class SessionStore:
    def __init__(self) -> None:
        self._docs: dict[str, Drawing] = {}
        self._history: dict[str, list[str]] = {}

    def create(self, dxf_bytes: bytes) -> str:
        try:
            doc = ezdxf.read(io.StringIO(dxf_bytes.decode("utf-8", errors="replace")))
        except Exception as e:  # ezdxf.DXFStructureError and friends
            raise ValueError(f"Not a valid DXF file: {e}") from e
        sid = uuid.uuid4().hex
        self._docs[sid] = doc
        self._history[sid] = []
        return sid

    def get(self, sid: str) -> Drawing | None:
        return self._docs.get(sid)

    def snapshot(self, sid: str) -> None:
        doc = self._docs[sid]
        buf = io.StringIO()
        doc.write(buf)
        self._history[sid].append(buf.getvalue())

    def undo(self, sid: str) -> bool:
        history = self._history.get(sid) or []
        if not history:
            return False
        snap = history.pop()
        self._docs[sid] = ezdxf.read(io.StringIO(snap))
        return True

    def serialize(self, sid: str) -> bytes:
        buf = io.StringIO()
        self._docs[sid].write(buf)
        return buf.getvalue().encode("utf-8")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/test_sessions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/app/sessions.py engine/tests/test_sessions.py && git commit -m "feat(engine): in-memory session store with snapshot/undo"
```

---

## Task 10: Wire the FastAPI endpoints

**Files:**
- Modify: `engine/app/main.py`
- Modify: `engine/tests/test_api.py`

Endpoints: `POST /sessions` (upload), `POST /sessions/{id}/chat`, `POST /sessions/{id}/undo`, `GET /sessions/{id}/dxf`. The Anthropic client is constructed lazily and overridable via dependency for tests.

- [ ] **Step 1: Write the failing tests**

Append to `engine/tests/test_api.py`:
```python
import io
from app import main
from app.sessions import SessionStore


def _fresh_store():
    main.store = SessionStore()  # reset between tests


def test_upload_returns_session_and_svg(sample_bytes):
    _fresh_store()
    r = client.post("/sessions", files={"file": ("plan.dxf", io.BytesIO(sample_bytes), "application/dxf")})
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body and body["svg"].lstrip().startswith("<")
    assert any(l["name"] == "WALLS" for l in body["summary"]["layers"])


def test_upload_rejects_garbage():
    _fresh_store()
    r = client.post("/sessions", files={"file": ("x.dxf", io.BytesIO(b"nope"), "application/dxf")})
    assert r.status_code == 422


def test_chat_applies_edit_and_rerenders(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)

    def fake_run_agent(**kwargs):
        from app import edits
        c = edits.add_wall(kwargs["doc"], 0, 0, 3, 0)
        return {"reply": "Added a wall.", "changes": [c]}

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())

    r = client.post(f"/sessions/{sid}/chat", json={"message": "add a wall"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "Added a wall."
    assert body["changes"][0]["op"] == "add_wall"
    assert body["svg"].lstrip().startswith("<")


def test_undo_endpoint(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    before = len(list(main.store.get(sid).modelspace()))
    main.store.snapshot(sid)
    from app import edits
    edits.add_wall(main.store.get(sid), 0, 0, 1, 1)

    r = client.post(f"/sessions/{sid}/undo")
    assert r.status_code == 200
    assert len(list(main.store.get(sid).modelspace())) == before


def test_download_dxf(sample_bytes):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    r = client.get(f"/sessions/{sid}/dxf")
    assert r.status_code == 200
    assert b"SECTION" in r.content  # DXF marker
```

- [ ] **Step 2: Run to verify fail**

Run: `cd engine && .venv/bin/pytest tests/test_api.py -v`
Expected: FAIL (new endpoints 404 / attributes missing)

- [ ] **Step 3: Implement endpoints**

Replace `engine/app/main.py`:
```python
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from app.agent import run_agent
from app.query import list_layers
from app.render import render_svg
from app.sessions import SessionStore

app = FastAPI(title="cad-designer engine")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:3000"],
    allow_methods=["*"], allow_headers=["*"],
)

store = SessionStore()
MODEL = os.environ.get("CAD_MODEL", "claude-sonnet-4-6")


def _anthropic_client():
    import anthropic
    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _summary(doc) -> dict:
    return {"layers": list_layers(doc)}


@app.post("/sessions")
async def create_session(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        sid = store.create(data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    doc = store.get(sid)
    return {"session_id": sid, "svg": render_svg(doc), "summary": _summary(doc)}


@app.post("/sessions/{sid}/chat")
def chat(sid: str, req: ChatRequest) -> dict:
    doc = store.get(sid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    store.snapshot(sid)
    out = run_agent(client=_anthropic_client(), doc=doc,
                    user_message=req.message, model=MODEL)
    if not out["changes"]:
        store.undo(sid)  # discard the no-op snapshot
    return {"reply": out["reply"], "changes": out["changes"],
            "svg": render_svg(store.get(sid))}


@app.post("/sessions/{sid}/undo")
def undo(sid: str) -> dict:
    doc = store.get(sid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    store.undo(sid)
    return {"svg": render_svg(store.get(sid))}


@app.get("/sessions/{sid}/dxf")
def download(sid: str):
    if store.get(sid) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    return Response(content=store.serialize(sid), media_type="application/dxf",
                    headers={"Content-Disposition": "attachment; filename=edited.dxf"})
```

- [ ] **Step 4: Run to verify pass**

Run: `cd engine && .venv/bin/pytest tests/ -v`
Expected: PASS (all engine tests)

- [ ] **Step 5: Commit**

```bash
git add engine/app/main.py engine/tests/test_api.py && git commit -m "feat(engine): upload/chat/undo/download endpoints"
```

- [ ] **Step 6: Manual smoke test**

```bash
cd engine && ANTHROPIC_API_KEY=sk-... .venv/bin/uvicorn app.main:app --reload
```
In another terminal upload a real DXF and chat. Verify SVG comes back and an edit applies.

---

# PHASE B — WEB UI

## Task 11: Scaffold Next.js + Vitest

**Files:**
- Create: `web/` via create-next-app, `web/vitest.config.ts`, `web/src/test-setup.ts`

- [ ] **Step 1: Scaffold**

Run from `cad-designer`:
```bash
npx create-next-app@latest web --typescript --app --no-tailwind --no-src-dir --eslint --use-npm --no-import-alias
```
Then move app into `src/` layout if create-next-app didn't (the plan assumes `web/src/app`). Adjust paths below to match the generated layout if needed.

- [ ] **Step 2: Add test deps + config**

```bash
cd web && npm install -D vitest @vitejs/plugin-react @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
```

`web/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test-setup.ts"] },
});
```

`web/src/test-setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```

Add to `web/package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 3: Verify a trivial test runs**

`web/src/__tests__/smoke.test.ts`:
```ts
import { describe, it, expect } from "vitest";
describe("smoke", () => it("works", () => expect(1 + 1).toBe(2)));
```
Run: `cd web && npm test`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add web/ && git commit -m "feat(web): scaffold Next.js with Vitest"
```

---

## Task 12: Typed engine client

**Files:**
- Create: `web/src/lib/api.ts`, `web/src/__tests__/api.test.ts`

- [ ] **Step 1: Write the failing test**

`web/src/__tests__/api.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { uploadDxf, sendChat, undo } from "../lib/api";

beforeEach(() => { vi.restoreAllMocks(); });

it("uploadDxf posts multipart and returns parsed body", async () => {
  const body = { session_id: "s1", svg: "<svg/>", summary: { layers: [] } };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const file = new File(["x"], "p.dxf");
  const res = await uploadDxf(file);
  expect(res.session_id).toBe("s1");
  expect((global.fetch as any).mock.calls[0][0]).toContain("/sessions");
});

it("sendChat posts json message", async () => {
  const body = { reply: "ok", changes: [], svg: "<svg/>" };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
  const res = await sendChat("s1", "move it");
  expect(res.reply).toBe("ok");
});

it("throws on non-ok", async () => {
  global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: "bad" }) });
  await expect(uploadDxf(new File(["x"], "p.dxf"))).rejects.toThrow();
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- api`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement client**

`web/src/lib/api.ts`:
```ts
const BASE = process.env.NEXT_PUBLIC_ENGINE_URL ?? "http://localhost:8000";

export type Layer = { name: string; entity_count: number };
export type UploadResult = { session_id: string; svg: string; summary: { layers: Layer[] } };
export type Change = { op: string; handle: string; summary: string };
export type ChatResult = { reply: string; changes: Change[]; svg: string };

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as any).detail ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function uploadDxf(file: File): Promise<UploadResult> {
  const fd = new FormData();
  fd.append("file", file);
  return asJson<UploadResult>(await fetch(`${BASE}/sessions`, { method: "POST", body: fd }));
}

export async function sendChat(sid: string, message: string): Promise<ChatResult> {
  return asJson<ChatResult>(await fetch(`${BASE}/sessions/${sid}/chat`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  }));
}

export async function undo(sid: string): Promise<{ svg: string }> {
  return asJson<{ svg: string }>(await fetch(`${BASE}/sessions/${sid}/undo`, { method: "POST" }));
}

export function downloadUrl(sid: string): string {
  return `${BASE}/sessions/${sid}/dxf`;
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- api`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/api.ts web/src/__tests__/api.test.ts && git commit -m "feat(web): typed engine API client"
```

---

## Task 13: Uploader component

**Files:**
- Create: `web/src/components/Uploader.tsx`, `web/src/__tests__/Uploader.test.tsx`

- [ ] **Step 1: Write the failing test**

`web/src/__tests__/Uploader.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Uploader } from "../components/Uploader";

it("calls onUpload with the chosen file", async () => {
  const onUpload = vi.fn();
  render(<Uploader onUpload={onUpload} />);
  const file = new File(["x"], "plan.dxf", { type: "application/dxf" });
  const input = screen.getByLabelText(/upload dxf/i) as HTMLInputElement;
  await userEvent.upload(input, file);
  expect(onUpload).toHaveBeenCalledWith(file);
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- Uploader`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement**

`web/src/components/Uploader.tsx`:
```tsx
"use client";

export function Uploader({ onUpload }: { onUpload: (f: File) => void }) {
  return (
    <label>
      Upload DXF
      <input
        type="file"
        accept=".dxf"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUpload(f);
        }}
      />
    </label>
  );
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- Uploader`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/components/Uploader.tsx web/src/__tests__/Uploader.test.tsx && git commit -m "feat(web): Uploader component"
```

---

## Task 14: SvgViewer with pan/zoom

**Files:**
- Create: `web/src/components/SvgViewer.tsx`, `web/src/__tests__/SvgViewer.test.tsx`

- [ ] **Step 1: Write the failing test**

`web/src/__tests__/SvgViewer.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { SvgViewer } from "../components/SvgViewer";

it("renders the provided svg markup", () => {
  const { container } = render(<SvgViewer svg='<svg data-testid="dwg"></svg>' />);
  expect(container.querySelector('[data-testid="dwg"]')).not.toBeNull();
});

it("shows a placeholder when svg is empty", () => {
  const { getByText } = render(<SvgViewer svg="" />);
  expect(getByText(/no drawing/i)).toBeTruthy();
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- SvgViewer`
Expected: FAIL

- [ ] **Step 3: Implement (wheel-zoom + drag-pan via CSS transform)**

`web/src/components/SvgViewer.tsx`:
```tsx
"use client";
import { useRef, useState } from "react";

export function SvgViewer({ svg }: { svg: string }) {
  const [scale, setScale] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number } | null>(null);

  if (!svg) return <div style={{ padding: 24 }}>No drawing loaded</div>;

  return (
    <div
      style={{ overflow: "hidden", width: "100%", height: "100%", cursor: "grab", background: "#fafafa" }}
      onWheel={(e) => setScale((s) => Math.min(20, Math.max(0.1, s - e.deltaY * 0.001)))}
      onMouseDown={(e) => (drag.current = { x: e.clientX - pos.x, y: e.clientY - pos.y })}
      onMouseUp={() => (drag.current = null)}
      onMouseLeave={() => (drag.current = null)}
      onMouseMove={(e) => {
        if (drag.current) setPos({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y });
      }}
    >
      <div
        style={{ transform: `translate(${pos.x}px, ${pos.y}px) scale(${scale})`, transformOrigin: "0 0" }}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- SvgViewer`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/components/SvgViewer.tsx web/src/__tests__/SvgViewer.test.tsx && git commit -m "feat(web): SvgViewer with pan/zoom"
```

---

## Task 15: ChatPanel + ChangeLog

**Files:**
- Create: `web/src/components/ChatPanel.tsx`, `web/src/components/ChangeLog.tsx`, `web/src/__tests__/ChatPanel.test.tsx`

- [ ] **Step 1: Write the failing test**

`web/src/__tests__/ChatPanel.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "../components/ChatPanel";

it("submits a message and clears the input", async () => {
  const onSend = vi.fn().mockResolvedValue(undefined);
  render(<ChatPanel messages={[]} onSend={onSend} busy={false} />);
  const input = screen.getByPlaceholderText(/describe a change/i);
  await userEvent.type(input, "move counter 2m left");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  expect(onSend).toHaveBeenCalledWith("move counter 2m left");
});

it("renders existing messages", () => {
  render(<ChatPanel messages={[{ role: "assistant", text: "Done." }]} onSend={vi.fn()} busy={false} />);
  expect(screen.getByText("Done.")).toBeTruthy();
});
```

- [ ] **Step 2: Run to verify fail**

Run: `cd web && npm test -- ChatPanel`
Expected: FAIL

- [ ] **Step 3: Implement**

`web/src/components/ChatPanel.tsx`:
```tsx
"use client";
import { useState } from "react";

export type Msg = { role: "user" | "assistant"; text: string };

export function ChatPanel({
  messages, onSend, busy,
}: { messages: Msg[]; onSend: (m: string) => void; busy: boolean }) {
  const [text, setText] = useState("");
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: 12 }}>
        {messages.map((m, i) => (
          <p key={i} style={{ color: m.role === "user" ? "#222" : "#0b6" }}>
            <b>{m.role === "user" ? "You" : "AI"}:</b> {m.text}
          </p>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) { onSend(text.trim()); setText(""); }
        }}
        style={{ display: "flex", gap: 8, padding: 12 }}
      >
        <input
          placeholder="Describe a change…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={busy}
          style={{ flex: 1 }}
        />
        <button type="submit" disabled={busy}>Send</button>
      </form>
    </div>
  );
}
```

`web/src/components/ChangeLog.tsx`:
```tsx
import type { Change } from "../lib/api";

export function ChangeLog({ changes, onUndo }: { changes: Change[]; onUndo: () => void }) {
  return (
    <div style={{ padding: 12, borderTop: "1px solid #eee" }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <b>Changes</b>
        <button onClick={onUndo} disabled={changes.length === 0}>Undo last</button>
      </div>
      <ul>{changes.map((c, i) => <li key={i}>{c.summary}</li>)}</ul>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npm test -- ChatPanel`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/components/ChatPanel.tsx web/src/components/ChangeLog.tsx web/src/__tests__/ChatPanel.test.tsx && git commit -m "feat(web): ChatPanel and ChangeLog"
```

---

## Task 16: Wire the main page

**Files:**
- Modify: `web/src/app/page.tsx`

Composes everything: upload → store session → render SVG; chat → append messages + changes, swap SVG; undo button.

- [ ] **Step 1: Implement page**

`web/src/app/page.tsx`:
```tsx
"use client";
import { useState } from "react";
import { Uploader } from "../components/Uploader";
import { SvgViewer } from "../components/SvgViewer";
import { ChatPanel, type Msg } from "../components/ChatPanel";
import { ChangeLog } from "../components/ChangeLog";
import { uploadDxf, sendChat, undo, downloadUrl, type Change } from "../lib/api";

export default function Home() {
  const [sid, setSid] = useState<string | null>(null);
  const [svg, setSvg] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [changes, setChanges] = useState<Change[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(file: File) {
    setError(null);
    try {
      const res = await uploadDxf(file);
      setSid(res.session_id);
      setSvg(res.svg);
      setMessages([{ role: "assistant", text: "Floor plan loaded. What should I change?" }]);
      setChanges([]);
    } catch (e) { setError(String(e)); }
  }

  async function handleSend(msg: string) {
    if (!sid) return;
    setMessages((m) => [...m, { role: "user", text: msg }]);
    setBusy(true); setError(null);
    try {
      const res = await sendChat(sid, msg);
      setSvg(res.svg);
      setMessages((m) => [...m, { role: "assistant", text: res.reply }]);
      setChanges((c) => [...c, ...res.changes]);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }

  async function handleUndo() {
    if (!sid) return;
    const res = await undo(sid);
    setSvg(res.svg);
    setChanges((c) => c.slice(0, -1));
  }

  return (
    <main style={{ display: "grid", gridTemplateColumns: "1fr 380px", height: "100vh" }}>
      <section style={{ borderRight: "1px solid #eee" }}>
        <div style={{ padding: 12, display: "flex", gap: 16, alignItems: "center" }}>
          <Uploader onUpload={handleUpload} />
          {sid && <a href={downloadUrl(sid)}>Download DXF</a>}
          {error && <span style={{ color: "crimson" }}>{error}</span>}
        </div>
        <div style={{ height: "calc(100vh - 56px)" }}><SvgViewer svg={svg} /></div>
      </section>
      <aside style={{ display: "flex", flexDirection: "column" }}>
        <ChatPanel messages={messages} onSend={handleSend} busy={busy} />
        <ChangeLog changes={changes} onUndo={handleUndo} />
      </aside>
    </main>
  );
}
```

- [ ] **Step 2: Verify all web tests pass**

Run: `cd web && npm test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/src/app/page.tsx && git commit -m "feat(web): compose main editor page"
```

- [ ] **Step 4: Full manual end-to-end**

```bash
# terminal 1
cd engine && ANTHROPIC_API_KEY=sk-... .venv/bin/uvicorn app.main:app --reload
# terminal 2
cd web && npm run dev
```
Open http://localhost:3000, upload a DXF, confirm it renders, type "add a label 'TEST' near the entrance", confirm the SVG updates and a change appears, click Undo, click Download.

---

## Task 17: README and run script

**Files:**
- Create: `README.md`, `dev.sh`

- [ ] **Step 1: Write README**

`README.md`: document prerequisites (Python 3.12+, Node 18+, `ANTHROPIC_API_KEY`), how to install both halves, and how to run (`./dev.sh` or the two manual commands). Note DXF-only and how to convert DWG→DXF externally (ODA File Converter).

`dev.sh`:
```bash
#!/usr/bin/env bash
set -e
( cd engine && .venv/bin/uvicorn app.main:app --reload --port 8000 ) &
( cd web && npm run dev ) &
wait
```

- [ ] **Step 2: Commit**

```bash
chmod +x dev.sh && git add README.md dev.sh && git commit -m "docs: README and dev run script"
```

---

## Self-Review notes (addressed)

- **Spec coverage:** upload (T10/T13), SVG render+viewer (T3/T14), NL edit via tools+agent (T6/T7/T8), units (T5), change log + undo (T9/T10/T15), download (T10/T12/T16), error handling (T10 422, T7 tool errors, T8 clarify-on-ambiguity via system prompt). All covered.
- **No placeholders:** every code step is concrete.
- **Type consistency:** `Change`/`ChatResult`/`UploadResult` shapes match between `api.ts`, endpoints, and components; tool arg names (`dx_m`, `x1_m`…) consistent between `tools.py` schemas and `dispatch`.
- **Known risk:** ezdxf SVG `get_string`/`Page` API varies by version — Task 3 Step 4 includes the check + fallback. create-next-app layout may differ from assumed `src/` — Task 11 notes adjusting paths.
