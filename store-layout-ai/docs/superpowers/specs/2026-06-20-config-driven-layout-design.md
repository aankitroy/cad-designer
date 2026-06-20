# Config-Driven Layout Generation — Design

**Date:** 2026-06-20
**Status:** Approved (pending spec review)
**Supersedes the runtime-codegen approach in:** `2026-06-20-layout-finetune-agent-design.md`

## Problem

Today the model emits a **Python script** of `placer.place(...)` calls, and
`engine/executor.py` strips a code fence and `exec()`s it against a sandboxed
`placer`. A smoke test against the base model exposed the failure mode: the model
wrapped its output in a ` ```python ` fence and hit the `max_tokens` cap before
closing it. `_strip_fence` requires a closing fence, so it returned the raw text
with the opening fence intact → `SyntaxError: invalid syntax` on line 1. All three
self-repair attempts hit the same error and no DXF was produced.

Root issues with runtime codegen:
- **Fragile** — any malformed/truncated generation crashes the whole script; one bad
  line discards every good placement.
- **Unsafe** — executes model-written code via `exec`, even if sandboxed.
- **Hard to learn** — free-form Python is a large target for a 7B LoRA.

## Goal

The model emits **structured configuration (JSON)**, not code. A deterministic
interpreter applies the config to the `Placer` engine. No `exec` at runtime.

**Scope decision (confirmed):** the config is an **explicit placement list** — the
model still decides every fixture's coordinates (learned from the expert layouts).
This is NOT a high-level rule-solver that computes coordinates from semantic choices;
that would be a different project and would undercut the fine-tune's purpose.

## Config schema

A single JSON object with a flat list of typed operations that map 1:1 onto the
existing `Placer` API (`place` / `rect` / `fire`):

```json
{
  "placements": [
    {"op": "place", "block": "JJ SH 900", "x": 310, "y": 8486, "rot": 90, "zone": "value wall"},
    {"op": "rect",  "x0": 1820, "y0": 15293, "x1": 2570, "y1": 16049, "layer": "LK-TV SCREEN"},
    {"op": "fire",  "x": 960, "y": 2000}
  ]
}
```

Per-op required fields:
- `place`: `block` (str), `x` (int), `y` (int); optional `rot` (int, default 0),
  `zone` (str, annotation only — replaces today's `#` comment), `layer`, `label`.
- `rect`: `x0`, `y0`, `x1`, `y1` (int), `layer` (str).
- `fire`: `x`, `y` (int).

Coordinates are LOCAL millimetres, identical convention to today
(`place` positions the block so its bbox-min lands at `(x, y)`).

## Components

### `engine/executor.py` — `apply_layout(config, shell_path, out_path)`
Replaces `run_script`. Returns the same `ExecResult` dataclass
(`error`, `dxf_path`, `placer`, `doc`) so the agent loop is unaffected.

Steps:
1. **Parse** — accept either a raw JSON object or one inside a ` ```json ` fence
   (reuse a tolerant extractor). On unparseable JSON → `ExecResult(error=...)`.
2. **Validate each op** — check `op` is known and required fields are present and the
   right type. **Malformed entries are skipped (logged into a warnings list), not
   fatal.** A truncated array that loses its last (partial) element still applies
   every complete element. If ZERO valid placements remain → `error` (nothing to do).
3. **Banned-block check** — reject the whole config if any `place.block` is in
   `BANNED_BLOCKS` (now an exact field comparison; no regex over source text).
4. **Apply** — load shell, import libraries, instantiate the keyword-friendly
   `_Placer`, and call `placer.place/rect/fire` per op. A single op that raises is
   caught and recorded as a warning; the rest continue.
5. **Save** DXF, return `ExecResult`.

No `compile`, no `exec`, no `__builtins__` sandbox.

### `data/rules.py` — `SYSTEM_PROMPT`
Rewrite the OUTPUT CONTRACT section: "emit ONLY a JSON object of the form
`{"placements": [ ... ]}`" and document the three op shapes. The NON-NEGOTIABLE
RULES (1–8) and `BANNED_BLOCKS` are unchanged.

### `data/reverse_engineer.py` — `fp_to_config(fp_path, origin=None)`
Same geometry logic as `fp_to_script`, but builds a Python dict
`{"placements": [...]}` instead of script lines. Zone heuristic moves from a
`#` comment to a `"zone"` field. Returns the dict (caller serializes).

### `data/build_dataset.py`
- `build_record` assistant content = `json.dumps(fp_to_config(...))`.
- `roundtrip_ok` validates via `apply_layout` instead of `run_script`.
- Regenerates `train.jsonl` / `valid.jsonl` (old Python-target files overwritten).

### `engine/agent.py`
- `design()` calls `apply_layout(script, ...)` (variable renamed `config`).
- On parse/validation error, the `repair_note` carries the JSON error + warnings so
  the model can self-correct.
- Auditor, self-repair loop (≤3), PNG render, return shape: **unchanged**.

### Unchanged
`engine/auditor.py`, `engine/app.py`, `engine/model.py`, `web/index.html`,
`skilllib.py`, the `Placer` engine.

## Data flow (unchanged shape, new payload)

```
shell DXF → derive_params → prompt → model emits JSON config
          → apply_layout (parse → validate → banned check → place) → ExecResult
          → structured_audit → (repair ≤3) → render PNG → DXF + PNG + audit
```

## Error handling

| Failure | Behavior |
|---------|----------|
| Unparseable JSON | `ExecResult.error` set; agent feeds it as repair note |
| Truncated/partial trailing element | skipped; remaining valid ops applied |
| One op missing/wrong-typed field | that op skipped + warning; others applied |
| Banned block referenced | whole config rejected with explicit error |
| Zero valid placements | `error` ("no valid placements") |
| A `placer.*` call raises | caught per-op, recorded as warning, continue |

The design principle: **degrade gracefully, never crash.** A garbled response should
still yield a partial layout the auditor can critique, not a hard failure.

## Testing (TDD)

Rewritten:
- `tests/test_executor.py` — drives `apply_layout`: happy path, fenced JSON,
  malformed JSON, truncated-array tolerance, per-op skip, banned-block rejection,
  zero-valid-placements error.
- `tests/test_build_dataset.py` — record assistant content parses as JSON config;
  round-trip via `apply_layout`.
- `tests/test_agent.py` — `generate_fn` returns JSON; repair note carries JSON errors.
- `tests/test_reverse_engineer.py` — `fp_to_config` returns a dict with valid ops.

New assertions: no `exec`/`compile` reachable in the apply path.

**Acceptance:** full suite green; `build_dataset` regenerates ≥11 pairs; smoke test
against the base model gets *past* `apply_layout` into the auditor (a failing audit
is acceptable — the point is the plumbing no longer dies at parse/exec).

## Out of scope
- High-level rule-solver / automatic coordinate computation.
- Fixing `derive_params` `target_fixtures` (the observed `1` is suspect — tracked
  separately, not part of this change).
- Fine-tuning the model (separate step once the dataset is regenerated).
```
