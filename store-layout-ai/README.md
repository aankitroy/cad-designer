# store-layout-ai

Self-contained pipeline: reverse-engineer Lenskart shell→FP DXF pairs → fine-tune
Qwen2.5-Coder-7B (MLX LoRA) → in-process FastAPI agent + web UI that turns a base
shell DXF into a finished store layout DXF + PNG + audit.

References `../lenskart-store-design/` (scripts, assets) read-only via `skilllib.py`.

## Setup
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    pip install -r finetune/requirements.txt   # MLX, Apple Silicon only

## Pipeline
    python -m data.build_dataset          # → data/train.jsonl, valid.jsonl, coverage_report.md
    bash finetune/train.sh                # LoRA fine-tune on M4 Pro
    bash finetune/fuse.sh                 # fuse adapters → finetune/models/lk-cad-finetuned
    uvicorn engine.app:app --reload       # serve agent + web
