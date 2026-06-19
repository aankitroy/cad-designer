# In-Chat Component Placement (Phase 1)

**Goal:** Let the user attach a DXF file to a chat message ("here's a chair — place it near the entrance"), have the AI import and place it into the floor plan, and edit placed components (move / rotate / delete) via chat.

**Status:** Design approved 2026-06-19. Phase 1 of 2 (Phase 2 = direct canvas manipulation, separate spec).

---

## Scope

**In scope**
- Attach one DXF file to a chat message (paperclip button in the chat input).
- Engine imports the attached DXF's modelspace geometry as a **named block** in the session drawing.
- AI places it via a `place_component` tool, resolving location from natural language.
- Imported block **persists for the session** — re-placeable by name without re-uploading.
- Unit reconciliation so the component lands at correct real-world size.
- Edit placed components via chat: `move_entity`, `delete_entity` (existing) + new `rotate_entity`.
- `query_entities` reports `INSERT` blocks by component (block) name.

**Out of scope (explicitly)**
- Direct canvas manipulation (select/drag/rotate with mouse) — Phase 2.
- A component library / saved-components panel.
- Multiple file attachments per message (one per message in v1).
- Placement by clicking the canvas (Phase 2; v1 is natural-language located).

---

## Architecture

Builds on the existing engine (`ezdxf`) + Claude tool-use loop. No new services.

- **Block import** (`engine/app/components.py`, new): read attached DXF bytes, import its
  modelspace entities into a new block definition in the session `doc`, named from the
  uploaded filename (sanitized, deduped). Uses `ezdxf.addons.importer.Importer` so layers /
  linetypes / nested blocks the component depends on come along.
- **Unit scaling:** compute `scale = component_meters_per_unit / base_meters_per_unit` from each
  doc's `$INSUNITS` so an inserted block matches the base drawing's real-world scale.
- **New tools** (`engine/app/tools.py`): `place_component`, `rotate_entity`. `query_entities`
  gains a `block` field on INSERT results (the referenced block name).
- **Chat endpoint** becomes multipart: optional `file` part alongside `message`.
- **Agent**: when a component was attached, the system/user context notes
  *"User attached component '<name>'. Available components: [...]."*

---

## Data flow

1. `POST /sessions/{id}/chat` (multipart: `message`, optional `file`).
2. If `file` present → `components.import_as_block(doc, bytes, filename)` → returns block name;
   add name to the session's component registry (set of imported block names).
3. Run the agent with the message + a context line listing available component names.
4. AI: `query_entities(...)` to locate the reference point, then
   `place_component(name, x_m, y_m, rotation_deg?, scale?)`.
5. Engine inserts the block (with unit scale × optional user scale), snapshots for undo,
   re-renders, returns `{reply, changes, svg, layers}`.

---

## Engine units / interfaces

- `place_component(doc, name, x, y, rotation_deg=0, scale=1.0)` → adds an `INSERT`; returns a
  Change `{op:"place_component", handle, before:None, after:name, summary}`.
- `rotate_entity(doc, handle, angle_deg)` → rotates entity about its insert/center point;
  Change `{op:"rotate_entity", ...}`. For INSERTs, set `dxf.rotation`; for other entities use
  `entity.rotate_z` about the entity's reference point.
- `import_as_block(doc, dxf_bytes, filename) -> str` (block name). Raises `ValueError` on a
  non-DXF / empty attachment.
- `meters_per_unit(doc) -> float` added to `units.py` (factor used by both placement scaling
  and existing `meters_to_drawing_units`).

Coordinates passed by the AI are in **meters** (consistent with existing tools) and converted
via the session's units.

---

## Error handling

- Non-DXF / unreadable attachment → chat returns 422 with a clear message; no placement.
- `place_component` with an unknown component name → tool returns an error result; the AI
  re-checks available components or asks the user (does not crash).
- Empty modelspace in the attachment → 422 ("attached DXF has no drawable geometry").
- Placement still snapshots before mutating, so undo reverts a placement.

---

## UI (web)

- `ChatPanel` gains a paperclip **attach button**; selecting a `.dxf` shows a removable chip
  (filename) above the input. On send, if a file is attached the request is multipart.
- `api.ts` `sendChat(sid, message, file?)` sends `multipart/form-data` when `file` is present,
  else the current JSON path.
- Existing live layer-chip refresh and change log already display the placement result.

---

## Testing (TDD)

**Engine (pytest)**
- `import_as_block`: a fixture component DXF imports as a block; block exists; modelspace
  unchanged until placed.
- `import_as_block` rejects garbage bytes (ValueError) and empty-geometry DXF.
- `place_component`: inserts an INSERT referencing the block at the scaled coordinates;
  unit scaling correct (component mm into a meters base → 0.001 scale).
- `rotate_entity`: sets rotation on an INSERT; raises EntityNotFound on bad handle.
- `query_entities` returns `block` name for INSERTs.
- Tool dispatch for `place_component` / `rotate_entity`.
- Chat endpoint: multipart with a file imports the block and exposes it to the agent
  (agent mocked); multipart with bad file → 422.

**Web (Vitest + RTL)**
- Attach button sets the filename chip; remove clears it.
- `sendChat` sends multipart when a file is attached, JSON otherwise.

---

## Stack / files

- Engine: `components.py` (new), `tools.py`, `edits.py` (rotate), `units.py` (meters_per_unit),
  `agent.py` (component context), `main.py` (multipart chat). Tests alongside.
- Web: `components/ChatPanel.tsx` (attach), `lib/api.ts` (multipart sendChat),
  `app/page.tsx` (pass file through). Tests alongside.
- Model unchanged (Claude Sonnet 4.6 tool loop).
