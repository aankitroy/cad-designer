# LENSKART SOLUTIONS LTD.
### Facilities & Store Design
## TECHNICAL IMPLEMENTATION DOCUMENT
### LLM Fine-Tuning for Automated Lenskart Store Layout Design

| Field | Value |
|---|---|
| **Platform** | Apple M4 Pro 24 GB \| Framework: MLX + mlx-lm |
| **Document Version** | v2.0 — M4 Pro Edition |
| **Date** | June 2026 |
| **Target Hardware** | Apple M4 Pro, 24 GB Unified Memory |
| **ML Framework** | Apple MLX + mlx-lm |
| **Prepared By** | NSO — Pan India Maintenance |

---

## 1. Executive Summary

This document defines the end-to-end technical approach for fine-tuning a Large Language Model (LLM) on an Apple M4 Pro MacBook (24 GB unified memory) to automate Lenskart retail store CAD layout design. The entire pipeline — data preparation, LoRA fine-tuning, inference serving, and compliance auditing — runs 100% locally using Apple's MLX framework. No cloud GPU spend is required.

The system fine-tunes **Qwen2.5-Coder-7B-Instruct** (4-bit quantised, ~4.5 GB on-disk) on curated `(base shell DXF → ezdxf Python script)` training pairs drawn from real Lenskart store layouts and the lenskart-store-design skill assets. Post fine-tuning, a designer supplies a bare shell DXF + 2–3 inputs and receives a rule-compliant layout script, audit report, and rendered PNG within minutes — entirely on-device.

> **Why MLX on M4 Pro?** Apple MLX uses unified memory (RAM = VRAM) with zero copy overhead. A 7B 4-bit model fine-tune on 200 examples takes 2–3 hours on M4 Pro at ~$0 cloud cost. `bitsandbytes` / CUDA-based QLoRA does NOT run on Apple Silicon — MLX is the correct native framework.

---

## 2. Platform Decision — Why MLX on M4 Pro

### 2.1 Why NOT CUDA/bitsandbytes on M4 Pro

- `bitsandbytes` (required for QLoRA on CUDA) has no Apple Silicon / Metal support — it simply will not install or run.
- PyTorch MPS backend exists but is incomplete — many fine-tuning ops (gradient checkpointing, fused attention) are unsupported or crash.
- Attempting to fine-tune DeepSeek-Coder-V2-Lite (16B) on M4 Pro 24 GB with HuggingFace + bitsandbytes is not possible.

### 2.2 Why MLX is the Right Choice

- MLX was designed by Apple ML Research from scratch for Apple Silicon's unified memory architecture — zero memory copies between CPU and GPU.
- `mlx-lm` natively supports LoRA and QLoRA fine-tuning for Qwen2, Llama, Mistral, Gemma, Phi, and more.
- The 24 GB unified memory pool handles a 7B 4-bit model (~4.5 GB weights) + LoRA gradients + activations comfortably, with headroom for macOS.

### 2.3 M4 Pro Hardware Profile

| Spec | Value |
|---|---|
| Unified Memory | 24 GB LPDDR5X — shared between CPU, GPU, Neural Engine |
| Memory Bandwidth | 273 GB/s — primary determinant of LLM inference speed |
| GPU Cores | 20-core GPU (M4 Pro) |
| Neural Engine | 16-core, 38 TOPS |
| Inference speed (7B 4-bit) | ~45–55 tokens/sec via MLX |
| Fine-tune training speed (7B 4-bit) | ~1,800–2,200 tokens/sec throughput; ~2–3 hrs for 2,000 iters |
| macOS memory reservation | ~3.5 GB — usable headroom ~20.5 GB |

---

## 3. Base Model Selection for M4 Pro

On M4 Pro 24 GB, the practical ceiling for fine-tuning is 7B–14B models at 4-bit quantisation. The recommended model for this use case is:

| Model | Params | Model Size (4-bit) | Tok/sec M4 Pro | Verdict |
|---|---|---|---|---|
| Qwen2.5-Coder-7B-Instruct | 7B | ~4.5 GB | 45–55 | **PRIMARY** — best Python/ezdxf fit, MLX-native, proven fine-tune |
| Qwen2.5-Coder-14B-Instruct | 14B | ~8.5 GB | 25–35 | **UPGRADE** — better geometric reasoning, still fits 24 GB |
| DeepSeek-Coder-V2-Lite (16B) | 16B MoE | ~10.4 GB | 30–40 | **INFERENCE only** — fine-tuning on MLX is experimental; use Qwen for training |
| Qwen3 Coder 30B-A3B (MoE) | 30B / 3B active | ~17 GB | 30–35 | **ADVANCED** — fits 24 GB for inference; fine-tuning needs 36 GB+ |

> **Recommendation:** Start with `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit`. It is pre-converted for MLX, available directly on HuggingFace, and fine-tunes stably on 24 GB. If post-training evaluation shows geometric accuracy below target, upgrade to `Qwen2.5-Coder-14B-4bit`.

---

## 4. MLX Environment Setup

### 4.1 Installation

```bash
# 1. Install MLX ecosystem
pip install mlx mlx-lm

# 2. Install supporting libraries
pip install ezdxf matplotlib numpy datasets huggingface_hub

# 3. Verify MLX is using Metal (Apple GPU)
python -c "import mlx.core as mx; print(mx.default_device())"
# → Device(gpu, 0)   <-- confirms Metal backend active
```

### 4.2 Download Pre-Quantised Model

```bash
# Option A — direct mlx-lm download (recommended)
mlx_lm.generate \
  --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --prompt "Write a hello world in Python"
```

```python
# Option B — Python API
from mlx_lm import load, generate
model, tokenizer = load('mlx-community/Qwen2.5-Coder-7B-Instruct-4bit')
response = generate(model, tokenizer, prompt='import ezdxf', max_tokens=200)
```

> **Memory Check:** After loading the 7B 4-bit model, Activity Monitor > Memory should show ~7–9 GB used (model + cache). Fine-tuning will peak at 16–19 GB. If you see >20 GB, reduce `--num-layers` in the training command.

---

## 5. Training Data Pipeline

### 5.1 Data Sources

The training data comes from three tiers, in order of priority:

| Tier | Source | Description |
|---|---|---|
| T1 — Gold | `assets/calibration/BASE 3 FP.dxf`, `BASE 2 FP.dxf` | Expert-designed finished layouts — reverse-engineer to Python scripts; highest quality training examples |
| T2 — Real | Historical store DXFs from past projects | Bulk corpus; shell extracted from finished DXF; reconstruct script from INSERT entities |
| T3 — Synthetic | §16 variant scripts + programmatically generated shells | Augment corpus to reach 150–300 examples; same shell, different valid layout approach |

### 5.2 Shell Extraction

```bash
# For each finished store DXF:
python scripts/extract_shell.py store_XX_finished.dxf
# Writes: store_XX.structure.json  (A-WALL bbox, columns, beams, doors, toilet)
# Writes: store_XX_shell.dxf       (structure layers only — no furniture)
```

### 5.3 Script Reverse-Engineering

Parse each finished DXF to extract INSERT entities and reconstruct ezdxf Placer API calls. Comments are critical — CAD-Coder research showed commented training code improves geometric reasoning significantly.

```python
import ezdxf
doc = ezdxf.readfile('store_XX_finished.dxf')
msp = doc.modelspace()

# Extract all furniture inserts
for e in msp.query('INSERT'):
    print(f"placer.place('{e.dxf.name}', x={e.dxf.insert.x:.0f}, y={e.dxf.insert.y:.0f}, rot={e.dxf.rotation:.0f})")

# Annotate with rule comments during reconstruction:
# PREMIUM WALL — Super-Premium → JJ-EYE → OD-EYE → JJ-SUN brand sequence
# CLINIC — loose nook flush to east perimeter wall (Rule 3)
# EURO SPINE — joined NON-DRAWER to NON-DRAWER (Rule 5)
```

### 5.4 JSONL Training Format (mlx-lm compatible)

`mlx-lm` expects JSONL with a `messages` key (ChatML format). Each record is one `(shell + params) → (annotated Python script)` pair.

```json
{"messages": [
  {"role": "system",
   "content": "You are a Lenskart store layout engineer. Given a base shell structure JSON and store parameters, generate a complete annotated ezdxf Python script producing a rule-compliant Lenskart store layout. Use ONLY blocks from BASE LIBRARY.dxf."},
  {"role": "user",
   "content": "SHELL:\n{shell_json}\n\nPARAMS:\nclinic_count: 2\ntarget_fixtures: 19\nentry_side: west\npremium_side: south"},
  {"role": "assistant",
   "content": "```python\n# Lenskart Store XX — 2-Clinic Layout\nimport ezdxf\n..."}
]}
```

Organise your data directory as `mlx-lm` expects:

```
data/
  train.jsonl   # 80% of records (~120–240 examples)
  valid.jsonl   # 20% of records (~30–60 examples)
```

> **Target Dataset Size:** Minimum 150 total records for meaningful fine-tuning. 300+ recommended. Use §16 layout variants to augment — each variant of an existing store is a valid additional training example at zero extra collection cost.

---

## 6. Fine-Tuning with mlx-lm on M4 Pro

### 6.1 Safe Hyperparameters for 24 GB

The key lesson from real M4 Pro fine-tuning attempts: `batch-size > 1` with long sequences (>1024 tokens) **WILL crash the Mac** by spiking past 23 GB. The safe configuration below is validated on 24 GB Apple Silicon:

| Parameter | Safe Value | Crash Risk if Higher | Rationale |
|---|---|---|---|
| `--batch-size` | 1 | Crashes at 2+ with long seqs | 7B model + long ezdxf scripts (800–1200 tokens) hits 20 GB at batch=1 |
| `--grad-accumulation-steps` | 4–8 | N/A | Effective batch = 4–8 without memory spike; accumulate gradients instead |
| `--num-layers` | 16 | OOM at 24+ | Controls how many transformer layers get LoRA adapters; 16 is sweet spot |
| `--max-seq-length` | 2048 | OOM at 4096+ | ezdxf scripts run 600–900 tokens; 2048 covers most with headroom |
| `--iters` | 1500–2000 | Overfitting | With 150–300 examples, sweet spot is 1500–2000 iters |
| `--learning-rate` | 1e-4 | Instability at 2e-4+ | Conservative LR for small datasets; prevents overshooting |
| `--clear-cache-threshold` | 0.8 | N/A | Clears MLX metal cache when >80% memory used — prevents OOM |

### 6.2 Training Command

```bash
python -m mlx_lm.lora \
  --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --train \
  --data ./data \
  --iters 2000 \
  --batch-size 1 \
  --grad-accumulation-steps 8 \
  --num-layers 16 \
  --learning-rate 1e-4 \
  --optimizer adamw \
  --max-seq-length 2048 \
  --clear-cache-threshold 0.8 \
  --steps-per-eval 100 \
  --val-batches 10 \
  --save-every 200 \
  --adapter-path ./adapters/lk-store-layout
```

> **Expected Training Time:** ~2–3 hours for 2,000 iterations on M4 Pro with the above settings. Monitor Activity Monitor > Memory — if pressure reaches 22 GB+, reduce `--num-layers` to 12 or `--max-seq-length` to 1536.

### 6.3 LoRA Configuration (mlx-lm default)

`mlx-lm` applies LoRA automatically. To customise rank and target layers, add a `lora_config.yaml`:

```yaml
# lora_config.yaml
lora_parameters:
  rank: 32             # Higher rank = more capacity; 32 is safe for 24 GB
  alpha: 64            # Scaling factor = 2x rank (standard)
  dropout: 0.05
  keys:                # Which layers to adapt
    - self_attn.q_proj
    - self_attn.k_proj
    - self_attn.v_proj
    - self_attn.o_proj
    - mlp.gate_proj
    - mlp.up_proj
    - mlp.down_proj
```

```bash
# Add to training command:
  --config lora_config.yaml
```

### 6.4 Monitor Training

Watch for `val_loss` reducing consistently. If it diverges or stays flat after 500 iters, stop and reduce learning rate to `5e-5`.

```bash
# mlx-lm prints per-step loss to stdout. Also watch memory in real time:
# Open Terminal 2 and run:
watch -n 2 'vm_stat | grep -E "Pages free|Pages active|Pages wired"'
# Or use Activity Monitor > Memory > Memory Pressure
# Green = safe. Yellow = monitor closely. Red = reduce settings immediately.
```

---

## 7. Model Fusing & Inference Setup

### 7.1 Fusing LoRA Adapters into Base Model

After training, fuse the LoRA adapters into the base weights to produce a single merged model for faster inference (no adapter overhead at runtime):

```bash
python -m mlx_lm.fuse \
  --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --adapter-path ./adapters/lk-store-layout \
  --save-path ./models/lk-cad-finetuned \
  --de-quantize false   # keep 4-bit quantisation post-fuse
```

### 7.2 Running Inference

```python
from mlx_lm import load, generate
import json

model, tokenizer = load('./models/lk-cad-finetuned')

def generate_layout(shell_json: dict, params: dict) -> str:
    prompt = tokenizer.apply_chat_template([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": f"SHELL:\n{json.dumps(shell_json)}\n\nPARAMS:\n{json.dumps(params)}"}
    ], tokenize=False, add_generation_prompt=True)
    return generate(model, tokenizer, prompt=prompt, max_tokens=4096, verbose=False)

# Example call:
shell = json.load(open('store_42.structure.json'))
params = {'clinic_count': 2, 'target_fixtures': 19, 'entry_side': 'west', 'premium_side': 'south'}
script = generate_layout(shell, params)
exec(script)   # produces store layout DXF
```

### 7.3 Local OpenAI-Compatible API Server

For integration with other tools (VS Code, scripts, web UI), serve the model as a local API:

```bash
mlx_lm.server \
  --model ./models/lk-cad-finetuned \
  --port 8080 \
  --max-tokens 4096

# Now accessible at http://localhost:8080/v1/chat/completions
# Compatible with any OpenAI SDK client
```

---

## 8. End-to-End Inference Pipeline

### 8.1 Flow

| # | Component | Detail |
|---|---|---|
| 1 | Shell Parsing | `python scripts/extract_shell.py uploaded_shell.dxf` → `structure.json` |
| 2 | Prompt Build | Serialize `structure.json` + user params (`clinic_count`, `target_fixtures`, `entry_side`, `premium_side`) |
| 3 | MLX Inference | Fine-tuned Qwen2.5-Coder-7B generates annotated ezdxf Python script (~600–900 tokens, ~15–20 sec on M4 Pro) |
| 4 | Script Execute | `subprocess.run(['python', '-c', script])` in sandboxed temp dir; captures DXF output |
| 5 | Audit | `compliance_audit.py` on output DXF — check 0 FAILs, 0 obstruction hits |
| 6 | Self-Repair | If FAILs > 0 and attempts < 3: append error + audit summary to context and regenerate |
| 7 | Render PNG | `dxf_engine.render_png` → PNG for visual review |
| 8 | Output | Return DXF + PNG + `audit_report.md` to designer |

### 8.2 Self-Repair Loop

```python
for attempt in range(3):
    script = generate_layout(shell_json, params)
    result = execute_script_sandboxed(script)
    if result.error:
        params['_error'] = f'Script error: {result.error[:300]}'
        continue
    audit = run_compliance_audit(result.dxf_path)
    if audit.fail_count == 0:
        break   # success
    params['_audit_fails'] = audit.fail_summary
# fallback: return best partial result with warning
```

---

## 9. Evaluation Framework

| Metric | Target | Measurement |
|---|---|---|
| Script execution pass rate | >= 90% | % of generated scripts running without Python errors |
| Compliance FAIL = 0 rate | >= 75% | % passing `compliance_audit.py` with zero FAILs |
| Column/beam obstruction = 0 | >= 98% | `audit.py [1][2]` hard constraint |
| Clinic island FAILs = 0 | >= 90% | `audit.py [4]` — clinics must be wall-flush |
| Bare wall spans = 0 | >= 85% | `audit.py [4]` — walls must be merchandised end-to-end |
| Fixture count within ±3 | >= 80% | Generated count vs. `target_fixtures` parameter |
| DXF round-trip success | >= 95% | `ezdxf.readfile()` on output DXF without errors |

---

## 10. Data Augmentation Strategies

If the real DXF corpus is small (<100 stores), augmentation is essential to reach the 150–300 target.

### 10.1 §16 Variant Generation

For each real store, generate 2–3 valid variant scripts from §16 Optimization Guide (L-shape clinic 2B, wall-heavy density, slim euro spine). Each is a new training example.

> Same shell + different layout approach = free additional labeled data.

### 10.2 Synthetic Shell Generation

Programmatically generate rectangular/L-shaped shells using `ezdxf` with randomised dimensions (8–20m wide, 6–15m deep), column placements, and door positions.

Run the existing skill workflow to produce expert layouts for these shells — each produces a new labeled pair.

### 10.3 Coordinate Perturbation

Jitter all coordinates in real training scripts by ±50–100mm. Produces near-identical but non-duplicate examples, improving the model's coordinate generalisation.

---

## 11. Memory Management on 24 GB

24 GB is tight for 7B fine-tuning. These practices prevent crashes:

| Practice | Action |
|---|---|
| Close memory-hungry apps | Quit Chrome, Docker Desktop, Xcode, Spotlight indexing before training run |
| Use `--clear-cache-threshold 0.8` | Tells MLX to flush the Metal shader cache when memory pressure exceeds 80% |
| Batch size = 1 always | With 800–1200 token ezdxf scripts, batch > 1 reliably OOMs on 24 GB |
| Gradient accumulation instead | Use `--grad-accumulation-steps 8` to simulate effective batch size of 8 |
| Cap `--max-seq-length` at 2048 | Most ezdxf scripts fit; if some training scripts are very long (>1800 tokens), truncate or split |
| Start with `--num-layers 12` | If OOM occurs, drop from 16 to 12 LoRA layers. Quality impact is minor. |
| Training at night / screensaver off | macOS may reclaim GPU memory for display compositing during training; disable screensaver |

---

## 12. Integration with lenskart-store-design Skill

### 12.1 What the Model Must Learn from the Skill

| Skill Non-Negotiable Rule | Encoding in Training Data |
|---|---|
| Use ONLY `BASE LIBRARY.dxf` blocks | Training scripts reference only valid block names; retired blocks (`LOOKER`, `POS`, `NESTING TABLES`) never appear |
| Never overlap column/beam | All coordinates validated by `audit.py [1][2]` before inclusion; obstruction > 0 = example excluded |
| Clinics flush to perimeter wall | All training examples use wall-nook clinic pattern; no clinic island examples in training set |
| Euro joining rule | Training scripts always place Euro pairs joined on non-drawer ±x faces with inline comment |
| Brand wall sequence | Premium wall: Super-Premium → JJ-EYE → OD-EYE → JJ-SUN → C-LENS breaker; each zone commented |
| Toilet door 750mm clear | Validated in compliance audit; examples failing this check excluded from training set |
| BOH behind door | Back-of-house consistently placed in rear wing with door drawn; labelled rectangles for storage |

---

## 13. Risks & Mitigations

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | Mac crash during training — memory spike kills the session | High | Use `batch-size=1`, `--clear-cache-threshold 0.8`, close all apps. If crashes persist, reduce `--num-layers` to 12 and `--max-seq-length` to 1536. |
| 2 | Coordinate hallucination — model generates geometrically wrong coordinates | High | Self-repair loop catches audit failures. Include A-WALL bbox dimensions in system prompt. Normalise training coordinates to LOCAL frame. |
| 3 | Small corpus (<100 stores) — overfitting, poor generalisation | High | Augment with §16 variants + synthetic shells. Apply dropout 0.05. Evaluate on diverse hold-out shells from different store shapes. |
| 4 | Retired block usage in generated scripts | Medium | System prompt explicitly lists banned block names. Add post-generation filter: regex scan output for banned block names before execution. |
| 5 | MLX version incompatibility — mlx-lm API changes frequently | Medium | Pin versions: `pip install mlx==0.26.x mlx-lm==0.19.x`. Test on a small dataset before full training run after any upgrade. |

---

## 14. Phased Rollout Plan (M4 Pro)

| Phase | Duration | Deliverable | Success Criterion |
|---|---|---|---|
| P1 | 1 week | Environment + data: MLX installed, 50+ JSONL records validated, `data/` directory ready | `mlx_lm.generate` works; 50 scripts all execute; `val.jsonl` has 10+ records |
| P2 | 2 days | First training run: 1,000 iters; evaluate on hold-out; confirm no OOM | Training completes without crash; `val_loss` < 0.8; script exec rate > 70% |
| P3 | 3 days | Full 2,000-iter run with augmented dataset (150+ records); best adapter saved | Compliance FAIL=0 rate > 60% on hold-out; clinic island rate < 15% |
| P4 | 2 days | Fuse adapters; local inference server on port 8080; self-repair loop integrated | End-to-end layout generation < 3 min; design team can test 5 real shells |
| P5 | Ongoing | Monitor quality; add new store DXFs to training set quarterly; retrain adapters | Compliance FAIL=0 rate > 80%; design team adoption > 50% of new stores |

---

## 15. Appendix — Quick Reference

### 15.1 Key MLX Commands Cheatsheet

| Action | Command |
|---|---|
| Install | `pip install mlx mlx-lm ezdxf datasets` |
| Test model | `mlx_lm.generate --model mlx-community/Qwen2.5-Coder-7B-Instruct-4bit --prompt "test"` |
| Train | `python -m mlx_lm.lora --model ... --train --data ./data --batch-size 1 --iters 2000` |
| Resume training | Add `--resume-adapter-file ./adapters/lk-store-layout/adapters.npz` to training command |
| Fuse adapters | `python -m mlx_lm.fuse --model ... --adapter-path ./adapters/... --save-path ./models/...` |
| Serve as API | `mlx_lm.server --model ./models/lk-cad-finetuned --port 8080` |
| Inference (Python) | `from mlx_lm import load, generate; model, tok = load('./models/lk-cad-finetuned')` |

### 15.2 Non-Negotiable Constraints for System Prompt

- **Block library:** `BASE LIBRARY.dxf` ONLY. Banned: `LOOKER`, `NESTING TABLES`, `POS`, generic `CABINET`, TV blocks (55"/49"/43"), `PICK UP COUNTER`, sofas, discussion tables.
- **Column/beam:** ZERO overlaps. Fixtures may butt faces but never overlap.
- **Clinics:** loose-furniture nooks FLUSH to perimeter wall. Never floor islands.
- **Euros:** join NON-DRAWER to NON-DRAWER. Drawers exposed on long edges (±y faces).
- **Toilet door:** 750mm clear approach. Door swing never blocked.
- **Fixture count:** wall + floor DISPLAY units only — excludes billing/greeter/AR/bench/clinic/BOH.
- **Fire safety:** minimum 3 extinguishers distributed front/mid/back.

---

*— End of Document — Lenskart Solutions Ltd. | v2.0 M4 Pro Edition | Internal Confidential —*
