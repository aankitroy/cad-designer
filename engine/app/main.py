import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

# Load engine/.env (e.g. ANTHROPIC_API_KEY) before anything reads the environment.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from app import components, space, tools, units
from app import view as view_mod
from app.agent import run_agent
from app.query import list_layers
from app.render import render_svg
from app.sessions import SessionStore

app = FastAPI(title="cad-designer engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = SessionStore()
MODEL = os.environ.get("CAD_MODEL", "claude-sonnet-4-6")

# session_id -> list of imported component (block) names
_components: dict[str, list[str]] = {}

# session_id -> orientation override edge (e.g. "north")
_orientation: dict[str, str] = {}

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
        elif e.dxftype() == "TEXT":
            label = e.dxf.text
        elif e.dxftype() == "MTEXT":
            label = e.text
        else:
            label = e.dxftype()
        out.append(
            {
                "handle": handle,
                "type": e.dxftype(),
                "label": label,
                "bbox": [bb.extmin.x, bb.extmin.y, bb.extmax.x, bb.extmax.y],
            }
        )
    return out


def _anthropic_client():
    import anthropic

    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


class UnitsRequest(BaseModel):
    units: str


class EditRequest(BaseModel):
    name: str
    args: dict


_MANUAL_OPS = {"move_entity", "rotate_entity", "delete_entity"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _summary(doc) -> dict:
    return {
        "layers": list_layers(doc),
        "units": units.current_units(doc),
        "unit_options": units.UNIT_NAMES,
    }


@app.post("/sessions")
async def create_session(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        sid = store.create(data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    doc = store.get(sid)
    return {
        "session_id": sid,
        "svg": render_svg(doc),
        "summary": _summary(doc),
        "view": view_mod.svg_view(doc),
    }


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
            name = components.import_as_block(
                doc, data, file.filename or "component.dxf"
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        _components.setdefault(sid, []).append(name)

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
    else:
        _record_changes(sid, out["changes"])
    current = store.get(sid)
    return {
        "reply": out["reply"],
        "changes": out["changes"],
        "svg": render_svg(current),
        "layers": list_layers(current),
        "view": view_mod.svg_view(current),
    }


@app.get("/sessions/{sid}/selectables")
def selectables(sid: str) -> dict:
    doc = store.get(sid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    return {
        "selectables": _selectable_entities(doc, sid),
        "view": view_mod.svg_view(doc),
    }


@app.post("/sessions/{sid}/units")
def set_units(sid: str, req: UnitsRequest) -> dict:
    doc = store.get(sid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    try:
        units.set_units(doc, req.units)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"units": units.current_units(doc)}


@app.post("/sessions/{sid}/undo")
def undo(sid: str) -> dict:
    doc = store.get(sid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    store.undo(sid)
    current = store.get(sid)
    return {
        "svg": render_svg(current),
        "layers": list_layers(current),
        "view": view_mod.svg_view(current),
    }


@app.post("/sessions/{sid}/edit")
def edit(sid: str, req: EditRequest) -> dict:
    doc = store.get(sid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    if req.name not in _MANUAL_OPS:
        raise HTTPException(status_code=400, detail=f"Unsupported edit op: {req.name}")

    store.snapshot(sid)
    out = tools.dispatch(doc, req.name, req.args)
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


@app.get("/sessions/{sid}/dxf")
def download(sid: str):
    if store.get(sid) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    return Response(
        content=store.serialize(sid),
        media_type="application/dxf",
        headers={"Content-Disposition": "attachment; filename=edited.dxf"},
    )
