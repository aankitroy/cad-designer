# cad-designer

Upload a 2D DXF floor plan, see it rendered, and edit it through natural-language
chat. The AI applies structured edits to the drawing's entities (move, add walls,
add labels, delete, re-layer) and the viewer re-renders live. Undo and download the
edited DXF at any time.

## How it works

- **`web/`** — Next.js (App Router, TypeScript) UI: file upload, pan/zoom SVG
  viewer, chat panel, change log + undo, download. Pure presentation; it never
  parses DXF itself.
- **`engine/`** — Python FastAPI service that owns all CAD logic (`ezdxf`) and the
  Claude tool-use loop (`anthropic` SDK). Sessions are held in memory.

Chat → Claude calls CAD tools (`query_entities`, `move_entity`, `add_wall`,
`add_text_label`, `delete_entity`, `set_layer`, `list_layers`) → edits applied with
`ezdxf` → modelspace re-rendered to SVG → returned to the browser.

## Prerequisites

- Python 3.12+
- Node 18+
- An Anthropic API key (`ANTHROPIC_API_KEY`)

## Setup

```bash
# engine
cd engine
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# web
cd ../web
npm install
```

## Run

```bash
export ANTHROPIC_API_KEY=sk-ant-...
./dev.sh
```

This starts the engine on `:8000` and the web app on `:3000`. Open
http://localhost:3000, upload a `.dxf`, and start editing by chat.

Or run the two halves manually:

```bash
# terminal 1
cd engine && ANTHROPIC_API_KEY=sk-ant-... .venv/bin/uvicorn app.main:app --reload --port 8000
# terminal 2
cd web && npm run dev
```

## Tests

```bash
cd engine && .venv/bin/pytest      # engine (pytest)
cd web && npm test                 # web (vitest)
```

## Configuration

- `ANTHROPIC_API_KEY` — required by the engine for chat.
- `CAD_MODEL` — Claude model for the agent loop (default `claude-sonnet-4-6`).
- `NEXT_PUBLIC_ENGINE_URL` — engine base URL the web app calls (default
  `http://localhost:8000`).

## Notes & limitations

- **DXF only.** DWG is a closed binary format; convert it to DXF first (e.g. with
  the free ODA File Converter) before uploading.
- Files are loaded in `ezdxf` **recover mode**, which tolerates the structural
  quirks common in DXFs exported by other CAD tools (non-unique handles, etc.).
- Geometry nested inside block references (`INSERT`) is expanded and rendered — a
  plan that looks blank in a block-unaware viewer will still render here.
- Individual entities that fail to render (e.g. a `LEADER` referencing a missing
  dimstyle) are skipped rather than blanking the whole drawing.
- Very large/complex drawings (tens of thousands of entities) produce large SVGs
  and slower re-renders; v1 targets typical floor-plan-sized files.
- Sessions are in-memory and single-user — this is a local tool, not a deployed
  multi-user service.
