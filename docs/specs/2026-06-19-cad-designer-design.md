# cad-designer — Natural-Language 2D Floor-Plan Editor

**Goal:** A local web app where you upload a 2D architectural CAD file (DXF), see it rendered, and edit it through natural-language chat. The AI applies structured edits to the drawing's entities and the viewer re-renders live.

**Status:** Design approved 2026-06-19. Local-first v1.

---

## Scope

**In scope (v1)**
- Upload a `.dxf` file.
- Render the drawing to SVG with pan/zoom.
- Chat-driven editing: natural language → structured edit operations applied via `ezdxf` → live re-render.
- Change log with undo.
- Download the edited DXF.

**Out of scope (fast-follows, explicitly deferred)**
- DWG upload / auto DWG→DXF conversion (convert externally for v1).
- Click-to-select entities in the viewer; drag-handle direct manipulation.
- Multi-user, authentication, cloud deployment.
- 3D / cad-skill (parametric 3D printing) — wrong domain, not used.

---

## Architecture

Two local processes:

### 1. Next.js app (UI) — `web/`
- App Router + TypeScript.
- Pure presentation + chat. Never parses or mutates DXF itself.
- Components: file upload, SVG viewer (pan/zoom), chat panel, change-log/undo, download button.
- Talks to the engine over HTTP (JSON + SVG strings).

### 2. Python FastAPI service (engine) — `engine/`
- Owns **all** CAD logic (`ezdxf`) **and** the Claude tool-use loop (`anthropic` Python SDK).
- Keeps parse / edit / render / AI orchestration in one place — no double round-trips.
- In-memory session store: `{session_id: {doc, history[]}}`.

Rationale: DXF editing in Node is weak; `ezdxf` is the mature tool and is already set up in the sibling `nso` project. Putting the Claude loop here too avoids forwarding tool calls across process boundaries.

---

## Data flow

1. **Upload** `POST /sessions` (multipart `.dxf`) → `ezdxf.readfile` → store under `session_id` → render SVG → `{session_id, svg, summary}`.
2. **Chat** `POST /sessions/{id}/chat {message}` → run Claude with CAD tools. Claude inspects (`query_entities`), then acts (`move_entity`, …) in a tool loop until it stops.
3. Apply edits via `ezdxf`, snapshot prior state to history, **re-render SVG**, return `{svg, changes[], reply}`.
4. **Undo** `POST /sessions/{id}/undo` → pop snapshot → re-render.
5. **Download** `GET /sessions/{id}/dxf` → serialize current doc.

Round-trip target: sub-second per edit = "real time."

---

## Claude tool vocabulary

Read:
- `list_layers()` — layer names + entity counts.
- `query_entities(layer?, type?, near_text?, near_point?, radius?)` — returns matching entities with handles, types, coordinates, and any associated text. This is how Claude resolves vague references like "the cash counter."

Write:
- `add_wall(x1,y1,x2,y2, layer?)` — LWPOLYLINE/LINE.
- `add_door(wall_handle, position, width)` — gap + swing arc on a wall.
- `add_text_label(x,y,text, layer?, height?)`.
- `insert_fixture(name, x,y, rotation?)` — INSERT from a small block library.
- `move_entity(handle, dx, dy)`.
- `delete_entity(handle)`.
- `set_layer(handle, layer)`.

**Units:** read `$INSUNITS` from the header; convert natural-language distances (e.g. "2m") to drawing units before applying.

All write ops return a `change` record `{op, handle, before, after, summary}` collected into the response `changes[]`.

---

## Rendering

`ezdxf.addons.drawing` with the SVG backend → SVG string returned to the frontend. Preserves layers and colors. Frontend renders the SVG inside a pan/zoom container (no client-side DXF parsing).

---

## Error handling

- Unparseable/non-DXF upload → 422 with a clear message.
- Claude requests an op on a missing handle → tool returns an error result; Claude re-queries or apologizes; no crash.
- Ambiguous reference ("which counter?") → Claude asks a clarifying question instead of guessing.
- Every edit snapshots first, so undo always works; a failed op leaves the doc unchanged.

---

## Testing (TDD)

**Engine (pytest)**
- Each edit op: load fixture DXF → apply → assert entity created/moved/deleted and `change` record correct.
- Unit conversion (`$INSUNITS` m→drawing units).
- Tool dispatch maps tool name → function with validated args.
- Claude loop with a **mocked** Anthropic client: given canned tool calls, assert ops applied and response shape.
- Undo restores prior state.

**Web (Vitest + RTL)**
- Upload renders the returned SVG.
- Chat submit posts message, shows reply + change-log entry, swaps SVG.
- Undo button calls endpoint and restores prior SVG.

---

## Stack

- **Web:** Next.js (App Router), TypeScript, Vitest + React Testing Library.
- **Engine:** Python 3.12 venv, FastAPI, `ezdxf`, `anthropic` Python SDK, pytest.
- **Model:** Claude **Sonnet 4.6** (`claude-sonnet-4-6`) for the interactive agent loop (low latency); upgradable to Opus 4.8.
- **Config:** `ANTHROPIC_API_KEY` via env. Engine on `:8000`, web on `:3000` (proxied).
