import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

# Load engine/.env (e.g. ANTHROPIC_API_KEY) before anything reads the environment.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from app import components, units
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


def _anthropic_client():
    import anthropic

    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


class UnitsRequest(BaseModel):
    units: str


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
    return {"session_id": sid, "svg": render_svg(doc), "summary": _summary(doc)}


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

    store.snapshot(sid)
    out = run_agent(
        client=_anthropic_client(),
        doc=doc,
        user_message=message,
        model=MODEL,
        components=_components.get(sid, []),
    )
    if not out["changes"]:
        store.undo(sid)  # discard the no-op snapshot
    current = store.get(sid)
    return {
        "reply": out["reply"],
        "changes": out["changes"],
        "svg": render_svg(current),
        "layers": list_layers(current),
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
    return {"svg": render_svg(current), "layers": list_layers(current)}


@app.get("/sessions/{sid}/dxf")
def download(sid: str):
    if store.get(sid) is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    return Response(
        content=store.serialize(sid),
        media_type="application/dxf",
        headers={"Content-Disposition": "attachment; filename=edited.dxf"},
    )
