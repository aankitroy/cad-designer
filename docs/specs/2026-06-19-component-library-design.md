# Searchable, Draggable Component Library (left panel)

**Goal:** A left-side panel listing a fixed library of DXF components (the Lenskart block
library, ~62 files) with thumbnails and name search. The user drags a component onto the
canvas to place it where they drop it. Placed library items behave like any other placed
component (selectable, draggable, rotatable, deletable, undoable).

**Status:** Design approved 2026-06-19. Builds on component placement, spatial awareness,
and manual canvas editing.

---

## Scope

**In scope**
- Engine reads a fixed folder of `.dxf` components (path from env) and serves a catalog.
- A cached SVG thumbnail per component (rendered via the existing renderer).
- A left panel: search box (filter by name) + scrollable list of thumbnail + name rows.
- Each row is draggable; dropping on the canvas places the component centered at the drop
  point, on a `Furniture` layer by default.
- Library placement reuses `import_as_block` (lazy, once per component per session) and
  `place_component` (center-align + unit scaling already implemented).
- Placed library items are normal selectable/editable entities.

**Out of scope (explicitly)**
- Adding / editing / deleting library files from the UI (folder is read-only).
- Categories, tags, or fuzzy search beyond case-insensitive name substring match.
- Multi-drop, drag-to-reorder, favorites/recents.
- Live drag-ghost of the *component artwork* while dragging from the panel (the native
  drag image / a simple cursor affordance is enough; the component appears on drop).
- Rendering thumbnails on the client (engine renders them).

---

## Architecture

Builds on the existing FastAPI + ezdxf engine and the Next.js viewer. No new services.

- **`engine/app/library.py` (new):** lists the component folder and resolves a component id
  to its file path. Pure/IO module, no FastAPI types.
- **`engine/app/main.py`:** three endpoints — catalog, thumbnail (cached), and
  place-from-library (lazy import + place). A per-session record of which library ids were
  already imported (reuses the existing `_components` registry name list).
- **`engine/app/render.py`:** unchanged; thumbnails call `render_svg` on the library doc.
- **Web `components/LibraryPanel.tsx` (new):** search + draggable thumbnail list.
- **Web `components/SvgViewer.tsx`:** accepts a drop on the canvas, converts the drop point
  to world meters, and calls an `onDropComponent(id, x_m, y_m)` callback.
- **Web `lib/viewmap.ts`:** add `svgToWorldMeters` (absolute SVG point → world meters).
- **Web `lib/api.ts`:** `getLibrary`, `thumbnailUrl`, `placeFromLibrary`.
- **Web `app/page.tsx`:** adds the left panel to the workspace and wires the drop handler.

---

## Interfaces

### `engine/app/library.py`

```
LIBRARY_DIR = os.environ.get(
    "CAD_LIBRARY_DIR",
    str(Path.home() / "Downloads" / "BASE_LIBRARY_components"),
)

def list_components(dir: str = LIBRARY_DIR) -> list[dict]:
    # [{"id": <sanitized stem>, "name": <filename stem>}], sorted by name.
    # id is a URL-safe slug derived from the filename; collisions disambiguated with a suffix.

def component_path(id: str, dir: str = LIBRARY_DIR) -> str | None:
    # Absolute path for an id, or None if unknown. Guards against path traversal
    # (id must map to a file directly inside dir).
```
`id` is derived once and stable: `re.sub(r"[^A-Za-z0-9_-]+", "-", stem)`, lowercased, with a
numeric suffix on collision. `list_components` and `component_path` derive ids the same way
so they agree.

### `engine/app/main.py`

```
GET  /library
     -> {"components": [{"id","name"}, ...]}

GET  /library/{id}/thumbnail.svg
     -> Response(media_type="image/svg+xml") of render_svg(<library doc>), cached in a
        module dict keyed by (path, mtime). 404 if id unknown / 422 if the DXF can't render.

POST /sessions/{sid}/library/place
     body: {"id": str, "x_m": float, "y_m": float, "rotation_deg"?: float, "layer"?: str}
     -> imports the library DXF as a block (once per session; block name tracked in
        _components[sid]); place_component centered at (x_m,y_m) on layer (default
        "Furniture"); snapshot for undo; record editable handle; return
        {"change", "svg", "view", "layers", "selectables"}  (same shape as /edit)
     -> 404 if id unknown; 422 if the component DXF has no geometry.
```
Thumbnail rendering reuses `sessions._read_dxf` (recover mode) to load the library file, then
`render_svg`. Cache entry invalidated when the file mtime changes.

### `web/lib/viewmap.ts`

```
svgToWorldMeters(view: View, sx: number, sy: number): [number, number]
    // Absolute SVG point -> world (drawing units), the inverse of worldToSvg, then -> meters.
    // s = viewBox.width / (xmax - xmin)
    //   xUnits = xmin + sx / s
    //   yUnits = ymax - sy / s          (Y flip)
    //   return [xUnits * meters_per_unit, yUnits * meters_per_unit]
    // Place endpoints expect meters, so the caller passes these straight through.
```

### `web/lib/api.ts`

```
type LibraryItem = { id: string; name: string };
getLibrary(): Promise<{ components: LibraryItem[] }>
thumbnailUrl(id: string): string                  // `${BASE}/library/${id}/thumbnail.svg`
placeFromLibrary(sid, id, x_m, y_m, rotation_deg?, layer?): Promise<EditResult>
```
`placeFromLibrary` returns the same `EditResult` shape as `manualEdit` (change/svg/view/
layers/selectables) so the page reuses the same state update.

### `web/components/LibraryPanel.tsx`

```
LibraryPanel({ items, onError }: { items: LibraryItem[]; onError?: (e: string) => void })
```
- A search `<input>`; filters `items` by case-insensitive substring of `name`.
- A scrollable list; each row: `<img src={thumbnailUrl(id)} loading="lazy">` + the name,
  with `draggable` set. On `dragStart`, `e.dataTransfer.setData("application/x-cad-component", id)`.

### `web/components/SvgViewer.tsx`

Add an optional prop `onDropComponent?: (id: string, x_m: number, y_m: number) => void`.
The `.canvas-stage` gets `onDragOver` (preventDefault to allow drop) and `onDrop`: read the
id from `dataTransfer`; if `view` and an id are present, convert the drop point via
`overlay.getScreenCTM().inverse()` then `svgToWorldMeters(view, ...)`, and call
`onDropComponent(id, x_m, y_m)`.

### `web/app/page.tsx`

- Loads the library once on mount (`getLibrary`).
- Renders `LibraryPanel` as a new left column; passes `onDropComponent` to `SvgViewer`.
- `onDropComponent` calls `placeFromLibrary(sid, id, x_m, y_m)`, then updates
  svg/view/layers/selectables/changes exactly like `handleEdit`.

---

## Data flow (drag a component in)

1. Panel loads `GET /library`; each row lazy-loads its thumbnail via `GET
   /library/{id}/thumbnail.svg`.
2. User drags a row over the canvas (`dataTransfer` carries the id).
3. Drop → SvgViewer converts the drop screen point to world meters and calls
   `onDropComponent(id, x_m, y_m)`.
4. Page → `POST /sessions/{sid}/library/place` → engine imports the block (once) and places
   it centered at the drop point.
5. Engine returns the new svg/view/selectables; the page swaps them; the component is now a
   selectable item the user can drag/rotate/delete.

---

## Error handling

- Unknown component id (catalog/thumbnail/place) → 404; the panel shows a broken-thumbnail
  fallback and the page surfaces a placement error.
- Library DXF with no drawable geometry → 422 on place (same message as attachments).
- Missing/empty `CAD_LIBRARY_DIR` → `GET /library` returns an empty list (panel shows an
  empty state); no crash.
- Drop when no drawing is loaded (`view` null) → no-op.
- Placement still snapshots first, so Undo reverts a dropped component.

---

## Testing (TDD)

**Engine (pytest)** — a temporary library dir fixture with 1-2 small DXFs:
- `list_components` lists the dir as `{id,name}`, sorted; ids are stable and unique.
- `component_path` resolves a known id; returns None / rejects traversal (`..`) for bad ids.
- `GET /library` returns the catalog.
- `GET /library/{id}/thumbnail.svg` returns SVG; a second request is served from cache
  (assert the renderer ran once via a spy/counter); unknown id → 404.
- `POST /library/place` imports the block once (second place of same id doesn't re-import)
  and places it centered at the given meters; returns selectables incl. the new handle;
  unknown id → 404.

**Web (Vitest + RTL)**
- `viewmap.svgToWorldMeters`: inverse of `worldToSvg`, Y-flip, mm + m cases.
- `api`: `getLibrary` / `placeFromLibrary` shapes; `thumbnailUrl` format.
- `LibraryPanel`: renders rows; typing in search filters by name; `dragStart` sets the
  dataTransfer payload.
- `SvgViewer`: a simulated drop with a component id calls `onDropComponent` with the
  expected `x_m/y_m` (CTM shimmed as in the existing tests).

---

## Stack / files

- Engine: `library.py` (new); `main.py` (catalog/thumbnail/place endpoints + thumbnail
  cache + per-session imported-id reuse). Tests alongside.
- Web: `components/LibraryPanel.tsx` (new), `lib/viewmap.ts` (`svgToWorldMeters`),
  `lib/api.ts` (`getLibrary`/`thumbnailUrl`/`placeFromLibrary`), `components/SvgViewer.tsx`
  (`onDropComponent` + drop handlers), `app/page.tsx` (left column + wiring),
  `app/globals.css` (left panel + thumbnail styles). Tests alongside.
- Config: `CAD_LIBRARY_DIR` env (defaults to the provided `BASE_LIBRARY_components/`).
- Model: unchanged; library placement never calls the AI.
