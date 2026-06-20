# Lenskart Layout Fine-Tuning + Web Agent — Design

**Date:** 2026-06-20
**Status:** Approved (design phase)
**Author:** brainstormed with Claude

---

## 1. Goal

Fine-tune a local LLM (MLX + Qwen2.5-Coder-7B on M4 Pro) to generate Lenskart store
layouts, and expose it as a web agent that takes a **base shell DXF** as input and
returns a **finished-product DXF** (+ PNG render + compliance audit report).

This round trains on the **12 usable shell→FP pairs** in `fine-turning/BASE FILES/`.
More pairs will be added later.

### Realistic goal for this round (decided)

**Prove the full pipeline end-to-end.** Fine-tuning a 7B model on 12 examples overfits
heavily and will not generalize to unseen shells yet. Success for this round =

- every stage runs and connects: data extraction → JSONL → MLX LoRA train → fuse →
  in-process serve → web agent → execute → audit → self-repair → DXF + PNG out, and
- the agent can **reproduce a held-out FP** for a shell close to its training set.

Generalization quality is explicitly deferred until more training data lands.

---

## 2. Key reframe

The existing `lenskart-store-design` skill already encodes the working approach: an LLM
**writes a `Placer`-API Python script** that, when executed against the bundled libraries,
produces the finished DXF. Fine-tuning therefore means teaching local Qwen to write that
script from a shell + a few params.

The 12 FP files are **finished DXFs, not the scripts that made them**. So the
highest-value, highest-risk work is the **data pipeline that reverse-engineers each FP
into a script**. If that is solid, everything downstream is plumbing.

**Consequence (de-risk):** the web agent can run on the **base (un-fine-tuned) Qwen +
in-context rules** from day one. Fine-tuning just swaps in better weights later. The web
product is not gated on 12-example training quality.

---

## 3. Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Training output representation | **Flat `placer.place('NAME', x, y, rot)` calls + labelled rectangles + rule comments**, in local coordinates. (Doc §5.3 style.) |
| Inference params source | **Auto-derive from shell + UI override.** Training params are derived from each FP so train/inference match. |
| Round goal | **Prove pipeline end-to-end** (quality deferred). |
| Model serving | **In-process load** inside FastAPI (`mlx_lm.load`/`generate`), not a separate `mlx_lm.server`. |
| Model bring-up order | **Base model first**, swap in fine-tuned/fused weights once trained. |
| Skill / auditor changes | **Allowed** — improve auditor (headless, structured) and skill (single-source rules) as needed. |

---

## 4. Coordinate frame

All generated scripts work in the **LOCAL frame** (world − A-WALL min), matching the skill
and the doc's coordinate-hallucination mitigation. `extract_shell` yields `(OX, OY)`;
`Placer.place` adds them back. Training targets emit local coords; the executor restores
the world offset.

---

## 5. Components

All new work lives in a single self-contained folder, **`store-layout-ai/`**:

```
store-layout-ai/
  README.md
  data/        # 5.1 data pipeline → train.jsonl / valid.jsonl + reports
  finetune/    # 5.2 MLX LoRA config + train/fuse scripts; adapters & fused model output here
  engine/      # 5.3 FastAPI app: in-process model, agent self-repair loop, executor
  web/         # 5.4 frontend: upload → params → run → preview → download
```

It **references** (does not duplicate) the existing skill's tooling and assets — these
stay the single source of truth and are upgraded in place per §5.5:

- `lenskart-store-design/scripts/` — `dxf_engine.py` (`Placer`), `extract_shell.py`,
  `audit.py`, `clinic_arrangements.py`
- `lenskart-store-design/assets/` — `BASE LIBRARY.dxf`, clinic libraries
- `lenskart-store-design/SKILL.md` + `references/` — the rule text (system prompt source)
- `fine-turning/BASE FILES/` — the 12 shell→FP training pairs

### 5.1 Data pipeline — `store-layout-ai/data/`  (the crux)

| Module | Responsibility | Depends on |
|---|---|---|
| `block_map.py` | Map every block name found across the 12 FPs → current library block, or a substitution rule (retired TV `55INCH`→rect on `LK-TV SCREEN`; storage/UPS/staff racks→labelled rect; pickup→`Pickup table PC`+rect; shell structure block `existignn csk`→skip). Emit a **coverage report** listing any unmapped block. | `BASE LIBRARY.dxf`, clinic libs |
| `reverse_engineer.py` | FP DXF → flat annotated `Placer` script. One `place()` per top-level INSERT (local coords + rotation), labelled `rect()` for substitutions. Adds **rule comments** via zone heuristics: which wall, brand sequence, euro-join, clinic, fire-extinguisher. | `block_map`, `extract_shell`, `dxf_engine` |
| `derive_params.py` | Extract `clinic_count`, `target_fixtures` (wall+floor display units only, per rule 4), `entry_side`, `premium_side` from each FP. | `extract_shell`, `block_map` |
| `build_dataset.py` | Per pair: `extract_shell` structure JSON + reverse-engineer FP script + derive params → one JSONL record. **Round-trip-validate** each (execute script → audit → confirm it reproduces the FP, e.g. matching insert counts/positions within tolerance) before inclusion. Split ~10 train / ~2 valid. | all of the above, `audit` |

**JSONL record shape** (`mlx-lm` ChatML, doc §5.4):

```json
{"messages": [
  {"role": "system",  "content": "<non-negotiable rules, from SKILL.md>"},
  {"role": "user",    "content": "SHELL:\n<structure_json>\n\nPARAMS:\n<params>"},
  {"role": "assistant","content": "```python\n<flat annotated Placer script>\n```"}
]}
```

**Single source of truth for rules:** the system prompt is generated from `SKILL.md` /
`FURNITURE PLACEMENT RULES.md` so training and inference share identical rule text.

**Output:** `finetune/data/train.jsonl`, `finetune/data/valid.jsonl`, plus a
`coverage_report.md` and per-pair round-trip pass/fail.

### 5.2 Fine-tuning — `store-layout-ai/finetune/`

MLX + `mlx-lm` LoRA, **config scaled down for 12 examples** (intentional overfit):

| Param | This round | Doc default (150+ ex) | Why |
|---|---|---|---|
| `--num-layers` | 8 | 16 | Tiny data; fewer adapters reduce noise |
| `--iters` | ~400 | 1500–2000 | Avoid pure memorization churn |
| `--learning-rate` | 5e-5 | 1e-4 | Conservative on tiny set |
| `--batch-size` | 1 | 1 | 24 GB safety |
| `--grad-accumulation-steps` | 4 | 8 | |
| `--max-seq-length` | 2048 | 2048 | ezdxf scripts fit |

Files: `requirements.txt` (pin `mlx`, `mlx-lm`, `ezdxf`…), `lora_config.yaml`,
`train.sh`, `fuse.sh`. Hold out 1–2 pairs (e.g. BASE 15) from training to measure
"unseen shell" vs "reproduce trained" behaviour.

### 5.3 Inference agent — `store-layout-ai/engine/` (FastAPI)

- **In-process** model load via `mlx_lm.load` at startup (base weights first; fuse-swap
  later). One service.
- `agent.py` — self-repair loop (doc §8.2): build prompt → `generate` script → execute
  sandboxed → `audit` → if FAILs and attempts < 3, append error+audit summary and
  regenerate → render PNG → return DXF + PNG + audit report. Falls back to best partial
  result with a warning.
- `executor.py` — sandboxed `exec` of the generated script with `Placer` + libraries in
  scope; captures the output DXF in a temp dir; applies the banned-block regex filter
  before execution (doc risk #4).
- Endpoints:
  - `POST /design` — multipart shell DXF + optional params → returns job id (or sync result).
  - `GET /design/{id}` — status + result paths.
  - `GET /design/{id}/dxf`, `/png`, `/report` — artifacts.

### 5.4 Web — `store-layout-ai/web/`

Upload shell DXF → backend auto-derives params → UI shows them **pre-filled and editable**
→ run → poll → render **PNG preview** + **audit report** + **DXF download**.

### 5.5 Auditor & rules — extended **inside** `store-layout-ai/`

Everything new stays in the new folder; the originals in `lenskart-store-design/` are
referenced **read-only**, not edited.

- **`store-layout-ai/engine/auditor.py`** — wraps/extends the existing `audit.py` to
  return a **structured result** (`{check, status, detail}[]`) consumable by the
  self-repair loop. Delegates the geometric primitives to the original `audit.py` so there
  is no logic fork, and adds circulation/access checks the prose rules require but the
  original auditor does not enforce:
  - `walk_around` (WARN) — flags pinch points where two major fixtures face each other
    with a gap in the trap range (~250–900 mm), too tight to walk (rules §5, §14, §15.6).
  - `door_access` (FAIL) — builds a swing/approach clearance zone per door from
    `structure["doors"]` (entry / toilet / BOH) and fails if any fixture overlaps it
    (SKILL rule 6, rules §15.3).
  - `washroom_access` (FAIL / N/A) — locates the toilet from `structure["labels"]` and
    fails if its approach zone is blocked (rules §2, §9, §15.3).
  - existing hard checks: `column_beam_overlap`, `fixture_overlap` (FAIL); plus
    `fixture_count`, `fire_extinguishers` (WARN). `passed = no FAIL`.
- **`store-layout-ai/data/rules.py`** (or `system_prompt.md`) — compiles the
  non-negotiable rules from `SKILL.md` / `FURNITURE PLACEMENT RULES.md` into a single
  string used as the system prompt by **both** dataset building and the agent. Generated
  from the source docs so there is one source of truth, but stored in the new folder.

---

## 6. Data flow (inference)

```
shell.dxf ──▶ extract_shell ──▶ structure.json
                                      │
            derive_params ────────────┤
                                      ▼
                          build prompt (rules + shell + params)
                                      ▼
                    mlx generate (in-process) ──▶ python script
                                      ▼
                    banned-block filter ──▶ executor (sandboxed)
                                      ▼
                               output.dxf
                                      ▼
                    audit ──FAILs>0 & try<3──▶ (repair: re-prompt) ─┐
                      │ pass                                         │
                      ▼                                             ─┘
              render_png + audit_report ──▶ return DXF + PNG + report
```

---

## 7. Testing strategy

- **P0 (no ML):** round-trip test — for each of the 12 pairs, reverse-engineer → execute
  → audit must reproduce the FP (insert-count/position match within tolerance) and
  produce 0 obstruction hits. This validates the data before any training.
- **Block-map coverage:** assert every FP block is mapped or explicitly substituted; fail
  the build on an unmapped block.
- **P1:** training completes on M4 Pro without OOM; val_loss decreases.
- **P2:** agent reproduces a **trained** example (sanity) and runs end-to-end on the
  **held-out** shell (BASE 15) producing a valid, round-trippable DXF.
- **P3:** web upload→download works against the running engine.

---

## 8. Phasing

| Phase | Deliverable |
|---|---|
| **P0** | Data pipeline + round-trip validation + block-map coverage (no ML). De-risks everything. |
| **P1** | Fine-tune + fuse on M4 Pro (scaled-down config). |
| **P2** | In-process inference agent + self-repair (works on base model even if FT is weak). |
| **P3** | Web wiring (upload → params → run → preview → download). |

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| FP blocks don't all map to the current library | `block_map` coverage report + build fails on unmapped block; substitutions for retired blocks. |
| 12 examples → severe overfit, no generalization | Explicitly the round goal is pipeline proof; scaled-down LoRA config; agent also works on base model + in-context rules. |
| Reverse-engineering is lossy | Round-trip validation per pair gates inclusion; mismatches reported, not silently dropped. |
| Coordinate hallucination at inference | Local-frame training; self-repair loop catches audit failures; A-WALL bbox in system prompt. |
| 24 GB OOM during training | batch=1, `--clear-cache-threshold 0.8`, `--num-layers` reducible to 8/6, close other apps. |
| Model emits retired/banned blocks | Banned-block regex filter before execution. |

---

## 10. Out of scope (this round)

- Generalization quality on arbitrary unseen shells.
- Multi-user / hosted deployment (local M4 Pro only).
- Separate OpenAI-compatible model server (`mlx_lm.server`) — using in-process load.
- Augmentation (§16 variants, synthetic shells, jitter) — later, to reach 150+ examples.
