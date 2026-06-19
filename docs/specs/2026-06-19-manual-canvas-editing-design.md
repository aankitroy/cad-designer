# Manual Drag-to-Edit on the Canvas (Phase 2b)

**Goal:** Let the user make small changes directly on the drawing — select a placed
item, drag it to move, rotate it with a handle, nudge it with arrow keys, and delete it —
without going through the AI chat. Edits apply through the existing `ezdxf` ops, snapshot
for undo, and re-render live.

**Status:** Design approved 2026-06-19. Phase 2b (direct canvas manipulation), building on
the component-placement and spatial-awareness work.

---

## Scope

**In scope**
- Select a session-added item (placed component INSERT or added text label) by clicking it
  on the canvas; show a selection box + rotate handle.
- **Move**: drag the selected item; commit on release.
- **Rotate**: drag the rotate handle; snap to 15°.
- **Delete**: Delete/Backspace key, or a button on the selection box.
- **Nudge**: arrow keys move the selection by ±0.1 m.
- A manual-edit endpoint that applies one edit op **without the AI**.
- Existing pan/zoom and Undo keep working; Undo covers manual edits.

**Out of scope (explicitly)**
- Selecting/editing the base shell (walls, columns, imported shell geometry) — locked.
- Multi-select, group move, marquee selection.
- Snapping to walls or other items; alignment guides.
- Resize / scale handles.
- Touch/mobile gestures (desktop mouse + keyboard only in v1).

---

## Architecture

Builds on the existing FastAPI + ezdxf engine and the Next.js viewer. No new services.

- **Render metadata (`render.py` / a small `view.py` helper):** every render-bearing
  response also returns a `view` describing the SVG↔world mapping.
- **Editable-entity registry (`main.py`):** a per-session set of handles the user/agent
  added, so only those are selectable. The base shell is never listed.
- **Manual-edit endpoint (`main.py`):** `POST /sessions/{id}/edit` runs ONE tool call
  through the existing `tools.dispatch` (reusing move/rotate/delete + unit conversion +
  error handling), snapshots for undo, and re-renders.
- **Selectables endpoint (`main.py`):** `GET /sessions/{id}/selectables` returns the live
  editable entities with world-space bounding boxes.
- **Viewer (`SvgViewer.tsx` + a pure `viewmap.ts`):** an overlay `<svg>` sharing the base
  SVG's viewBox draws selection boxes; pointer/keyboard handlers drive the edits.

### Coordinate model (verified)

ezdxf's `SVGBackend` with an auto-sized `Page(0,0)` emits a `viewBox` that is the world
bounding box scaled uniformly (longer side = 1,000,000), aspect preserved, origin `(0,0)`,
Y-flipped (DXF y-up → SVG y-down). Verified: synthetic 10×8 → viewBox `0 0 1000000 800000`
(aspect 1.25); BASE CAD → `0 0 440753 1000000` (aspect 0.4408) — both equal to the world
aspect. So the mapping is a single uniform scale + Y-flip:

```
s = VW / (world_xmax - world_xmin)      # == VH / (world_ymax - world_ymin)
svg_x = (world_x - world_xmin) * s
svg_y = (world_ymax - world_y) * s      # Y flip
# inverse (for drag deltas):
world_dx =  svg_dx / s
world_dy = -svg_dy / s                  # Y flip
meters_dx = world_dx * meters_per_unit
```

The overlay `<svg>` uses the **same viewBox** as the base SVG and sits in the same
container with the same CSS transform, so selection boxes drawn at `svg_x/svg_y` align with
the rendered drawing automatically. Screen↔viewBox conversion uses the browser's
`overlay.getScreenCTM().inverse()`, which already accounts for the pan/zoom CSS transform
and `preserveAspectRatio` letterboxing — so the frontend never re-derives that math.

---

## Interfaces

### `engine/app/view.py` (new)

```
def svg_view(doc) -> dict | None:
    # Returns the SVG<->world mapping for the current modelspace, or None if empty:
    # {
    #   "world": [xmin, ymin, xmax, ymax],   # drawing units (ezdxf.bbox.extents)
    #   "viewBox": [0, 0, VW, VH],           # VW/VH: longer side = 1_000_000, aspect kept
    #   "meters_per_unit": float,
    # }
```
`VW`/`VH` are computed the same way ezdxf does (`1_000_000 / max(world_w, world_h)` scale)
so the value matches the rendered SVG without parsing it. A unit test asserts the computed
viewBox matches the viewBox in `render_svg(doc)`.

### `engine/app/main.py`

- `_editable: dict[str, set[str]] = {}` — session → set of handles the user/agent added.
- Helper `_record_changes(sid, changes)`: for each change whose op is `place_component`,
  `add_text_label`, or `add_wall` and whose `handle` is non-empty, add the handle; for
  `delete_entity`, discard the handle. Called from both `chat` and `edit`.
- `_selectable_entities(doc, sid) -> list[dict]`: for each live handle in `_editable[sid]`,
  return `{handle, type, label, bbox}` where `bbox = [xmin,ymin,xmax,ymax]` in **drawing
  units** (`ezdxf.bbox.extents([entity])`, the same space as `view.world` so the frontend
  maps it directly). `label` is the block name for INSERTs or the text for TEXT. Skips
  dead/missing handles.

Endpoints:
```
GET  /sessions/{id}/selectables -> {"selectables": [...], "view": <svg_view>}
POST /sessions/{id}/edit  body: {"name": str, "args": object}
     # name in {"move_entity","rotate_entity","delete_entity"} (validated; 400 otherwise)
     # runs tools.dispatch(doc, name, args) after store.snapshot(sid)
     # on dispatch error -> 422 with the error; undo the snapshot
     # on success -> record changes, return:
     #   {"change": <change>, "svg": ..., "view": ..., "layers": ...,
     #    "selectables": [...]}
```
The existing `chat` and `undo` responses also gain `"view"` (and `chat` calls
`_record_changes`). Upload (`POST /sessions`) gains `"view"` in its body.

### `web/lib/viewmap.ts` (new, pure)

```
type View = { world: [number,number,number,number]; viewBox: [number,number,number,number]; meters_per_unit: number };

// all of view.world and bbox are in DRAWING UNITS; only svgDeltaToMeters crosses to meters
worldToSvg(view, wx, wy): [number, number]
svgRectFromBBox(view, bbox): { x, y, width, height }        // bbox in drawing units -> selection box
svgDeltaToMeters(view, dxSvg, dySvg): [number, number]      // svg -> drawing units (/s) -> meters (×mpu), Y-flip
```

### `web/lib/api.ts`

```
type View = ...                     // mirror of viewmap View
type Selectable = { handle: string; type: string; label: string; bbox: [number,number,number,number] };  // drawing units
getSelectables(sid): Promise<{ selectables: Selectable[]; view: View | null }>
manualEdit(sid, name, args): Promise<{ change; svg; view; layers; selectables }>
```
`UploadResult` / `ChatResult` / undo result types gain `view: View | null`.

### `web/components/SvgViewer.tsx`

Props gain: `selectables: Selectable[]`, `view: View | null`,
`onEdit(name, args) => Promise<void>`, `onSelect(handle | null)`.
An absolutely-positioned overlay `<svg>` (same `viewBox`, same transform wrapper as the
base) renders:
- a selection box around the selected entity's `bbox` (mapped via `viewmap`),
- a rotate handle above the box.

Pointer logic:
- `pointerdown` on the overlay: hit-test the click point (via `getScreenCTM().inverse()`)
  against selectable svg-rects (topmost-smallest wins); set selection. Empty space →
  clear selection and fall through to panning.
- drag on a selected box → track svg delta → on `pointerup`, `svgDeltaToMeters` →
  `onEdit("move_entity", {handle, dx_m, dy_m})`.
- drag on the rotate handle → angle from box center, snapped to 15° → on release,
  `onEdit("rotate_entity", {handle, angle_deg})`.
- key handlers (when something is selected): Delete/Backspace → `onEdit("delete_entity",
  {handle})`; arrows → `onEdit("move_entity", {dx_m, dy_m})` by ±0.1 m.

### `web/app/page.tsx`

Holds `selectables` + `view` state; fetches `getSelectables` after upload and after each
chat/edit; passes them and an `onEdit` (calls `manualEdit`, swaps svg/view/layers/
selectables, appends to the change log) into `SvgViewer`.

---

## Data flow (a move)

1. User clicks a placed item → overlay hit-test selects its handle.
2. User drags → overlay shows the box following the pointer (svg space).
3. On release → `svgDeltaToMeters(view, dxSvg, dySvg)` → `POST /edit
   {name:"move_entity", args:{handle, dx_m, dy_m}}`.
4. Engine: snapshot → `dispatch` (meters→units, `edits.move_entity`) → re-render → return
   `{svg, view, selectables, change}`.
5. Frontend swaps the SVG, refreshes selectables/view, adds the change to the log.

---

## Error handling

- `POST /edit` with an unknown `name` → 400. With a missing/stale handle → `dispatch`
  returns an error → 422 with the message; the snapshot is undone so nothing changes.
- Frontend shows the error and refetches `selectables` (handles may be stale after an
  external change).
- Empty modelspace → `view` is `null`; the overlay renders nothing and interactions no-op.
- Every `/edit` snapshots before mutating, so the existing **Undo** reverts manual edits.

---

## Testing (TDD)

**Engine (pytest)**
- `view.svg_view`: world extents + computed viewBox match the viewBox in `render_svg(doc)`
  (synthetic doc); aspect preserved; `None` for empty modelspace.
- `_record_changes`: placing a component records its handle; deleting removes it.
- `GET /selectables`: lists a placed component, excludes base-shell walls, drops a handle
  after its entity is deleted; includes `view`.
- `POST /edit` move: `move_entity` with `dx_m` moves the entity (meters→units) and returns
  a fresh `view`; rotate sets rotation; delete removes it and it leaves `selectables`.
- `POST /edit` validation: unknown `name` → 400; bad handle → 422; snapshot undone on error.

**Web (Vitest)**
- `viewmap`: `worldToSvg` / `svgRectFromBBox` / `svgDeltaToMeters` correct incl. Y-flip
  and `meters_per_unit` (mm and m cases).
- `api`: `getSelectables` and `manualEdit` shapes.
- `SvgViewer`: clicking a selectable sets selection (calls `onSelect`); a simulated drag of
  the box calls `onEdit("move_entity", …)` with the expected `dx_m/dy_m`; Delete key calls
  `onEdit("delete_entity", …)`; arrow key calls `move_entity` by ±0.1 m. (Hit-testing math
  is exercised through `viewmap` unit tests; component tests stub `getScreenCTM`.)

---

## Stack / files

- Engine: `view.py` (new), `main.py` (`_editable`, `_record_changes`, `/edit`,
  `/selectables`, `view` in responses), `render.py` (unchanged; `view.py` mirrors its
  scaling). Tests alongside.
- Web: `lib/viewmap.ts` (new), `lib/api.ts` (`getSelectables`, `manualEdit`, `view` types),
  `components/SvgViewer.tsx` (overlay + interactions), `app/page.tsx` (state + wiring),
  `app/globals.css` (selection box / handle styles). Tests alongside.
- Model: unchanged; manual edits never call the AI.
