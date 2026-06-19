import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile

# Load engine/.env (e.g. ANTHROPIC_API_KEY) before anything reads the environment.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

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
    out = run_agent(
        client=_anthropic_client(), doc=doc, user_message=req.message, model=MODEL
    )
    if not out["changes"]:
        store.undo(sid)  # discard the no-op snapshot
    return {
        "reply": out["reply"],
        "changes": out["changes"],
        "svg": render_svg(store.get(sid)),
    }


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
    return Response(
        content=store.serialize(sid),
        media_type="application/dxf",
        headers={"Content-Disposition": "attachment; filename=edited.dxf"},
    )
