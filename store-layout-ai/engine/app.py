"""FastAPI app: upload a shell DXF, auto-derive params, run the agent, download artifacts.
Model is loaded in-process via engine.agent's default generate (GENERATE_FN=None)."""
import os
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
import skilllib
from data.derive_params import derive_params
from engine.agent import design

app = FastAPI(title="Lenskart Layout Agent")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK_DIR = os.path.join(ROOT, "engine", "_jobs")
GENERATE_FN = None  # tests monkeypatch this; None → agent uses the in-process MLX model


def _save_upload(shell: UploadFile, job_dir):
    os.makedirs(job_dir, exist_ok=True)
    path = os.path.join(job_dir, "shell.dxf")
    with open(path, "wb") as f:
        shutil.copyfileobj(shell.file, f)
    return path


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(ROOT, "web", "index.html")) as f:
        return f.read()


@app.post("/derive")
def derive(shell: UploadFile = File(...)):
    job_dir = os.path.join(WORK_DIR, "derive-" + uuid.uuid4().hex[:8])
    path = _save_upload(shell, job_dir)
    return JSONResponse(derive_params(path))


@app.post("/design")
def design_endpoint(shell: UploadFile = File(...), clinic_count: int = Form(2),
                    target_fixtures: int = Form(19), entry_side: str = Form("west"),
                    premium_side: str = Form("south")):
    job_id = uuid.uuid4().hex[:12]
    job_dir = os.path.join(WORK_DIR, job_id)
    path = _save_upload(shell, job_dir)
    params = {"clinic_count": clinic_count, "target_fixtures": target_fixtures,
              "entry_side": entry_side, "premium_side": premium_side}
    res = design(path, params, out_dir=job_dir, generate_fn=GENERATE_FN)
    res_public = {k: v for k, v in res.items() if k != "doc"}
    res_public["job_id"] = job_id
    return JSONResponse(res_public)


@app.get("/design/{job_id}/dxf")
def get_dxf(job_id: str):
    return FileResponse(os.path.join(WORK_DIR, job_id, "layout.dxf"), filename="layout.dxf")


@app.get("/design/{job_id}/png")
def get_png(job_id: str):
    return FileResponse(os.path.join(WORK_DIR, job_id, "layout.png"), media_type="image/png")
