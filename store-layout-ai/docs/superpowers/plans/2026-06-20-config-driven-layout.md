# Config-Driven Layout Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace runtime Python codegen + `exec()` with a model-emitted JSON layout config applied by a deterministic, crash-tolerant interpreter.

**Architecture:** The model outputs `{"placements": [...]}` (typed `place`/`rect`/`fire` ops). A new `apply_layout()` parses (tolerant of code fences and truncation), validates per-op (skipping malformed entries), rejects banned blocks, and dispatches to the existing `Placer` API. No `exec`/`compile`. New functions are added alongside the old ones, callers migrated one at a time, and dead code removed last — so the test suite stays green after every task.

**Tech Stack:** Python 3.14, `ezdxf`, `pytest`, the `skilllib` bridge to `lenskart-store-design` (`Placer`, `load_shell`, `import_library`, `audit`).

**Spec:** `docs/superpowers/specs/2026-06-20-config-driven-layout-design.md`

**Working dir for all commands:** `/Users/aankitroy/Workspace/geoiq/cad-designer/store-layout-ai`
Activate the venv first in each shell: `source .venv/bin/activate`

## File Structure

- `engine/executor.py` — add `apply_layout()` + JSON parse/recover/validate/dispatch helpers; keep `run_script` until Task 6. One responsibility: turn a config string into an `ExecResult`.
- `data/reverse_engineer.py` — add `fp_to_config()` returning a dict; keep `fp_to_script` until Task 6.
- `data/rules.py` — rewrite `SYSTEM_PROMPT` OUTPUT CONTRACT to JSON; `BANNED_BLOCKS` unchanged.
- `data/build_dataset.py` — emit JSON assistant content; round-trip via `apply_layout`.
- `engine/agent.py` — call `apply_layout`; surface warnings in repair note.
- `tests/test_executor.py`, `tests/test_reverse_engineer.py`, `tests/test_build_dataset.py`, `tests/test_agent.py`, `tests/test_rules.py` — updated/added tests.

---

### Task 1: `apply_layout` in executor (core interpreter)

**Files:**
- Modify: `engine/executor.py` (add new code; leave `run_script` intact)
- Test: `tests/test_executor.py` (append new tests)

- [ ] **Step 1: Write the failing tests** — append to `tests/test_executor.py`:

```python
import json
from engine.executor import apply_layout


def _cfg(placements):
    return json.dumps({"placements": placements})


def test_apply_simple_config_to_dxf(tiny_shell, tmp_path):
    cfg = _cfg([{"op": "place", "block": "EURO 1040 x 1175", "x": 2000, "y": 1500, "rot": 0}])
    out = tmp_path / "out.dxf"
    res = apply_layout(cfg, tiny_shell, str(out))
    assert res.error is None
    assert os.path.isfile(out)
    assert len(res.placer.placed) == 1
    ezdxf.readfile(out)  # round-trips


def test_apply_accepts_fenced_json(tiny_shell, tmp_path):
    cfg = "```json\n" + _cfg([{"op": "place", "block": "EURO 1040 x 1175", "x": 2000, "y": 1500}]) + "\n```"
    res = apply_layout(cfg, tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is None and len(res.placer.placed) == 1


def test_apply_recovers_truncated_array(tiny_shell, tmp_path):
    # third object is cut off (no closing brace / fence) — the two complete ones must still apply
    text = ('{"placements": [\n'
            '{"op":"place","block":"EURO 1040 x 1175","x":2000,"y":1500},\n'
            '{"op":"place","block":"EURO 1040 x 1175","x":4000,"y":1500},\n'
            '{"op":"place","block":"EURO 1040 x')
    res = apply_layout(text, tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is None
    assert len(res.placer.placed) == 2
    assert res.warnings  # recovery recorded a warning


def test_apply_skips_invalid_op(tiny_shell, tmp_path):
    cfg = _cfg([{"op": "place", "block": "EURO 1040 x 1175", "x": 2000, "y": 1500},
                {"op": "place", "block": "EURO 1040 x 1175"}])  # missing x/y
    res = apply_layout(cfg, tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is None
    assert len(res.placer.placed) == 1
    assert res.warnings


def test_apply_rejects_banned_block(tiny_shell, tmp_path):
    cfg = _cfg([{"op": "place", "block": "55INCH", "x": 0, "y": 0}])
    res = apply_layout(cfg, tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is not None and "banned" in res.error.lower()


def test_apply_unparseable_returns_error(tiny_shell, tmp_path):
    res = apply_layout("not json at all <<<", tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is not None


def test_apply_zero_valid_placements_errors(tiny_shell, tmp_path):
    cfg = _cfg([{"op": "frobnicate", "x": 1}])
    res = apply_layout(cfg, tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is not None and "no valid placements" in res.error.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_executor.py -q`
Expected: FAIL — `ImportError: cannot import name 'apply_layout'`

- [ ] **Step 3: Implement** — add to `engine/executor.py` (keep the existing `run_script`, `_strip_fence`, `_check_banned`, `_Placer`, `ExecResult`). First give `ExecResult` a `warnings` field, then add the new code:

Change the dataclass (add the import and field):

```python
from dataclasses import dataclass, field
```

```python
@dataclass
class ExecResult:
    error: Optional[str]
    dxf_path: Optional[str]
    placer: Optional[object]
    doc: Optional[object]
    warnings: list = field(default_factory=list)
```

Add the new interpreter below `run_script`:

```python
_REQUIRED = {
    "place": ("block", "x", "y"),
    "rect": ("x0", "y0", "x1", "y1", "layer"),
    "fire": ("x", "y"),
}


def _extract_json(text):
    """Body of a ```json fence if present (closing fence optional, handles truncation),
    else the raw text."""
    m = re.search(r"```(?:json)?\s*(.*?)(?:```|\Z)", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def _recover_objects(text):
    """Best-effort: return every complete top-level {...} object found in `text`,
    each individually json-parseable. A trailing truncated object is dropped."""
    objs, depth, start, in_str, esc = [], 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    objs.append(json.loads(text[start:i + 1]))
                except Exception:
                    pass
                start = None
    return objs


def parse_config(text):
    """Return (placements_list, warnings). Tolerant of code fences, a bare top-level
    array, and truncation. Raises ValueError only when nothing usable is found."""
    body = _extract_json(text)
    try:
        obj = json.loads(body)
        if isinstance(obj, dict) and isinstance(obj.get("placements"), list):
            return obj["placements"], []
        if isinstance(obj, list):
            return obj, []
    except Exception:
        pass
    idx = body.find('"placements"')
    arr_start = body.find("[", idx) if idx != -1 else body.find("[")
    if arr_start == -1:
        raise ValueError("no placements array found in config")
    objs = _recover_objects(body[arr_start + 1:])
    if not objs:
        raise ValueError("no complete placement objects recovered from config")
    return objs, ["recovered from malformed/truncated JSON"]


def _valid_op(p):
    return isinstance(p, dict) and p.get("op") in _REQUIRED \
        and all(k in p for k in _REQUIRED[p["op"]])


def _dispatch(placer, p):
    op = p["op"]
    if op == "place":
        kw = {k: p[k] for k in ("layer", "label") if k in p}
        placer.place(p["block"], x=int(p["x"]), y=int(p["y"]), rot=int(p.get("rot", 0)), **kw)
    elif op == "rect":
        placer.rect(int(p["x0"]), int(p["y0"]), int(p["x1"]), int(p["y1"]), layer=p["layer"])
    elif op == "fire":
        placer.fire(int(p["x"]), int(p["y"]))


def apply_layout(config_text, shell_path, out_path):
    """Parse a JSON layout config and build the DXF deterministically (no exec).
    Malformed entries are skipped (recorded in warnings); only a banned block or an
    empty/garbled config is a hard error."""
    try:
        placements, warnings = parse_config(config_text)
    except Exception as e:
        return ExecResult(error=f"config parse error: {e}", dxf_path=None, placer=None, doc=None)
    warnings = list(warnings)
    valid = []
    for p in placements:
        if _valid_op(p):
            valid.append(p)
        else:
            warnings.append(f"skipped invalid op: {str(p)[:80]}")
    if not valid:
        return ExecResult(error="no valid placements in config", dxf_path=None,
                          placer=None, doc=None, warnings=warnings)
    banned = _check_banned_ops(valid)
    if banned:
        return ExecResult(error=banned, dxf_path=None, placer=None, doc=None, warnings=warnings)
    try:
        doc, msp, OX, OY = skilllib.load_shell(shell_path)
        skilllib.import_library(doc)
        skilllib.import_clinic_rooms(doc)
        placer = _Placer(doc, msp, OX, OY)
        for p in valid:
            try:
                _dispatch(placer, p)
            except Exception as e:
                warnings.append(f"op {p.get('op')} failed: {str(e)[:80]}")
        doc.saveas(out_path)
        return ExecResult(error=None, dxf_path=out_path, placer=placer, doc=doc, warnings=warnings)
    except Exception:
        return ExecResult(error=traceback.format_exc(limit=4), dxf_path=None,
                          placer=None, doc=None, warnings=warnings)


def _check_banned_ops(placements):
    names = {str(p.get("block", "")).upper() for p in placements if p.get("op") == "place"}
    for b in BANNED_BLOCKS:
        if b.upper() in names:
            return f"banned block referenced: {b}"
    return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_executor.py -q`
Expected: PASS (all old `run_script` tests + the 7 new `apply_layout` tests)

- [ ] **Step 5: Commit**

```bash
git add engine/executor.py tests/test_executor.py
git commit -m "feat(layout-ai): JSON config interpreter apply_layout (no exec)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `fp_to_config` in reverse_engineer

**Files:**
- Modify: `data/reverse_engineer.py` (add `fp_to_config`; keep `fp_to_script`)
- Test: `tests/test_reverse_engineer.py` (append new tests)

- [ ] **Step 1: Write the failing tests** — append to `tests/test_reverse_engineer.py`:

```python
from data.reverse_engineer import fp_to_config


def test_config_has_place_ops():
    fp = os.path.join(skilllib.BASE_FILES, "BASE 2 FP.dxf")
    cfg = fp_to_config(fp)
    assert isinstance(cfg, dict)
    blocks = [p["block"] for p in cfg["placements"] if p["op"] == "place"]
    assert "EURO 1040 x 1175" in blocks


def test_config_skips_shell_block():
    fp = os.path.join(skilllib.BASE_FILES, "BASE 2 FP.dxf")
    cfg = fp_to_config(fp)
    assert "existignn csk" not in [p.get("block") for p in cfg["placements"]]


def test_config_ops_all_known():
    fp = os.path.join(skilllib.BASE_FILES, "BASE 2 FP.dxf")
    cfg = fp_to_config(fp)
    assert all(p["op"] in ("place", "rect", "fire") for p in cfg["placements"])
    assert any(p.get("zone") for p in cfg["placements"] if p["op"] == "place")
```

- [ ] **Step 2: Run to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_reverse_engineer.py -q`
Expected: FAIL — `ImportError: cannot import name 'fp_to_config'`

- [ ] **Step 3: Implement** — add to `data/reverse_engineer.py` below `fp_to_script` (reuse the existing `_local_bbox`, `_zone_comment`, `STORE_SCALE`, `classify`):

```python
def fp_to_config(fp_path, origin=None):
    """Same geometry as fp_to_script, emitted as a layout config dict
    {"placements": [...]} of place/rect/fire ops instead of a Python script."""
    doc, msp, OX, OY = skilllib.load_shell(fp_path)
    if origin is not None:
        OX, OY = origin
    struct = skilllib.extract_structure(fp_path)
    wb = struct.get("wall_bbox") or (0, 0, 1, 1)
    wall_h = max(1, wb[3] - wb[1])

    placements, placed = [], 0
    for e in msp.query("INSERT"):
        name = e.dxf.name
        kind, target = classify(name)
        if kind == "skip":
            continue
        box = _local_bbox(e, OX, OY)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        rot = round(e.dxf.rotation or 0)
        if kind in ("library", "clinic_room"):
            placements.append({"op": "place", "block": target, "x": x0, "y": y0,
                               "rot": rot, "zone": _zone_comment(y0, wall_h)})
            placed += 1
        elif kind == "fire":
            placements.append({"op": "fire", "x": (x0 + x1) // 2, "y": (y0 + y1) // 2})
        elif kind == "substitute":
            placements.append({"op": "rect", "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                               "layer": target["layer"], "label": target["label"]})
        else:  # unmapped anonymous block
            if (x1 - x0) > STORE_SCALE or (y1 - y0) > STORE_SCALE:
                continue
            placements.append({"op": "rect", "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                               "layer": "LK-FURNITURE"})
    if placed == 0:
        raise ValueError(f"no placeable inserts in {fp_path}")
    return {"placements": placements}
```

- [ ] **Step 4: Run to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_reverse_engineer.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/reverse_engineer.py tests/test_reverse_engineer.py
git commit -m "feat(layout-ai): fp_to_config emits JSON layout config

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Rewrite `SYSTEM_PROMPT` to the JSON contract

**Files:**
- Modify: `data/rules.py` (replace the `SYSTEM_PROMPT` string; `BANNED_BLOCKS` unchanged)
- Test: `tests/test_rules.py` (append a contract test)

- [ ] **Step 1: Write the failing test** — append to `tests/test_rules.py`:

```python
from data.rules import SYSTEM_PROMPT


def test_prompt_specifies_json_contract():
    assert '{"placements"' in SYSTEM_PROMPT
    assert '"op"' in SYSTEM_PROMPT
    assert "```python" not in SYSTEM_PROMPT  # no longer asks for a Python script
```

- [ ] **Step 2: Run to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_rules.py -q`
Expected: FAIL — assertion on `'{"placements"'`

- [ ] **Step 3: Implement** — replace the entire `SYSTEM_PROMPT = """..."""` block in `data/rules.py` with:

```python
SYSTEM_PROMPT = """You are a Lenskart store-layout engineer. Given a base shell structure \
JSON and store parameters, output a JSON layout configuration that places furniture to \
produce a rule-compliant Lenskart store layout.

OUTPUT CONTRACT
- Emit ONLY a single JSON object of the form {"placements": [ ... ]}. No prose, no \
explanation, no Python, no code fences.
- Each element of "placements" is exactly one of:
  - {"op": "place", "block": "<BLOCK NAME>", "x": <int>, "y": <int>, "rot": <deg>, \
"zone": "<note>"} — a library fixture. Coordinates are LOCAL millimetres (x east of the \
A-WALL min, y north of it); the block is positioned so its bounding-box minimum corner \
lands at (x, y). "rot" and "zone" are optional ("rot" defaults to 0; "zone" is a free-text \
annotation such as "premium wall", "value wall", "euro spine", "clinics", "BOH", "toilet").
  - {"op": "rect", "x0": <int>, "y0": <int>, "x1": <int>, "y1": <int>, "layer": "<layer>"} \
— a substitution: TV screens on layer "LK-TV SCREEN", storage/UPS/staff racks on a \
labelled layer.
  - {"op": "fire", "x": <int>, "y": <int>} — a fire extinguisher.

NON-NEGOTIABLE RULES
1. Use ONLY blocks from BASE LIBRARY.dxf. Banned (never emit as a "place" block): LOOKER, \
NESTING TABLES, POS, generic CABINET, PICK UP COUNTER, discussion/D-tables, sofas, and \
55/49/43-inch TV blocks. Substitute TVs with an "op":"rect" on layer "LK-TV SCREEN"; \
storage/UPS/staff racks with a labelled "op":"rect".
2. NEVER overlap a column or beam. Treat every column/beam box in the shell JSON as a hard \
no-overlap zone. A fixture may butt a face but never overlap.
3. Clinics sit toward the back, flush to a perimeter wall (never floor islands); each opens on \
its long side onto a clear corridor, never at the toilet door.
4. Euros join NON-DRAWER to NON-DRAWER (side-by-side in x); never drawer-to-drawer.
5. Premium wall brand sequence (as you enter): super-premium -> JJ-EYE -> OD-EYE -> JJ-SUN, \
with a C-LENS as category breaker. Mirror every 2-3 wall fixtures.
6. Reuse the existing toilet; keep its door swing + approach clear. Give BOH a door.
7. Fixture count = wall + floor DISPLAY units only (wall units + euros + blue zero); the target \
is approximate, over preferred. At least 3 fire extinguishers, distributed front/mid/back.
8. CIRCULATION & ACCESS. Customers must be able to walk around: keep >=900 mm (ideally \
1100-1200) clear between facing floor fixtures and on every side of euros/islands that is not \
joined to another euro. Keep EVERY door's swing arc and approach clear — the entry door, the \
washroom door, and the BOH door — never place a fixture in a door's swing. The washroom must \
stay reachable via a clear approach passage (not through retail, not behind cash).

Walls run continuously from the glazing line to the back partition. Work entirely in the LOCAL \
frame. Output the JSON object only."""
```

- [ ] **Step 4: Run to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_rules.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/rules.py tests/test_rules.py
git commit -m "feat(layout-ai): system prompt emits JSON config, not Python

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Migrate `build_dataset` to config + regenerate dataset

**Files:**
- Modify: `data/build_dataset.py:7-11` (imports), `:42` (`build_record`), `:50-52` (`roundtrip_ok`)
- Test: `tests/test_build_dataset.py` (update `test_build_record_shape`)

- [ ] **Step 1: Update the failing test** — replace `test_build_record_shape` in `tests/test_build_dataset.py` and add the `json` import at top:

```python
import json
```

```python
def test_build_record_shape():
    shell, fp = discover_pairs()[0]
    rec = build_record(shell, fp)
    roles = [m["role"] for m in rec["messages"]]
    assert roles == ["system", "user", "assistant"]
    assert "SHELL:" in rec["messages"][1]["content"]
    assert "PARAMS:" in rec["messages"][1]["content"]
    cfg = json.loads(rec["messages"][2]["content"])
    assert isinstance(cfg["placements"], list) and cfg["placements"]
    assert any(p.get("op") == "place" for p in cfg["placements"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_build_dataset.py::test_build_record_shape -q`
Expected: FAIL — `json.loads` raises on the current Python-script assistant content

- [ ] **Step 3: Implement** — edit `data/build_dataset.py`:

Change the imports (lines 7–11) from `fp_to_script` / `run_script` to the config equivalents and add `json` (already imported at top):

```python
from data.rules import SYSTEM_PROMPT
from data.reverse_engineer import fp_to_config
from data.derive_params import derive_params
from data.block_map import coverage
from engine.executor import apply_layout
```

In `build_record`, change the assistant line:

```python
    assistant = json.dumps(fp_to_config(fp_path))
```

In `roundtrip_ok`, change the execution call (the first two lines of the body):

```python
def roundtrip_ok(rec, shell_path, out_path):
    config = rec["messages"][2]["content"]
    res = apply_layout(config, shell_path, out_path)
    if res.error:
        return False, res.error
```

(The rest of `roundtrip_ok` — `ezdxf.readfile`, wall-bbox check, column audit — is unchanged.)

- [ ] **Step 4: Run to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_build_dataset.py -q`
Expected: PASS (all three tests)

- [ ] **Step 5: Regenerate the dataset**

Run: `source .venv/bin/activate && python -m data.build_dataset`
Expected: prints `OK`/`SKIP` per pair and `wrote train=... valid=...` with at least 11 included. `data/train.jsonl` and `data/valid.jsonl` now contain JSON-config assistant turns.

Verify: `head -1 data/train.jsonl | python -c "import json,sys; d=json.load(sys.stdin); c=json.loads(d['messages'][2]['content']); print('placements:', len(c['placements']))"`
Expected: prints a positive placement count.

- [ ] **Step 6: Commit**

```bash
git add data/build_dataset.py tests/test_build_dataset.py data/train.jsonl data/valid.jsonl data/coverage_report.md
git commit -m "feat(layout-ai): dataset targets are JSON config; regenerate jsonl

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Migrate the agent to `apply_layout`

**Files:**
- Modify: `engine/agent.py:7` (import), `:30-49` (loop body)
- Test: `tests/test_agent.py` (rewrite fakes to return JSON)

- [ ] **Step 1: Update the failing tests** — replace the top of `tests/test_agent.py` (the import line and `fake_generate_ok`) and the flaky fn inside `test_design_self_repairs`:

```python
# tests/test_agent.py
import os
import json
import skilllib
from engine.agent import design


def fake_generate_ok(system, user):
    return json.dumps({"placements": [
        {"op": "place", "block": "EURO 1040 x 1175", "x": 2000, "y": 1500, "rot": 0},
        {"op": "fire", "x": 500, "y": 500},
        {"op": "fire", "x": 2000, "y": 2000},
        {"op": "fire", "x": 3500, "y": 3500},
    ]})
```

In `test_design_self_repairs`, replace the `flaky` first-attempt return with a config that lands a euro on the column (`y=0` → on the tiny_shell column at local (2000,0)-(2300,300)):

```python
    def flaky(system, user):
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps({"placements": [
                {"op": "place", "block": "EURO 1040 x 1175", "x": 2000, "y": 0}]})  # on column → FAIL
        return fake_generate_ok(system, user)
```

- [ ] **Step 2: Run to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_agent.py -q`
Expected: FAIL — `agent.design` still calls `run_script`, so a JSON string is treated as a Python script and errors (no `placer.place` calls run; audit/`ok` assertions fail)

- [ ] **Step 3: Implement** — edit `engine/agent.py`. Change the import on line 7:

```python
from engine.executor import apply_layout
```

Replace the loop body (lines 30–49) with:

```python
    for attempt in range(1, max_attempts + 1):
        user = build_user_prompt(shell_path, params, repair_note)
        config = generate_fn(SYSTEM_PROMPT, user)
        dxf_path = os.path.join(out_dir, "layout.dxf")
        res = apply_layout(config, shell_path, dxf_path)
        if res.error:
            repair_note = f"Config error: {res.error[:300]}"
            last = {"ok": False, "attempts": attempt, "error": res.error, "config": config}
            continue
        report = structured_audit(res.placer, struct, target_count=params.get("target_fixtures"))
        if report["passed"]:
            png_path = os.path.join(out_dir, "layout.png")
            skilllib.render_png(res.doc, png_path)
            return {"ok": True, "attempts": attempt, "dxf": dxf_path, "png": png_path,
                    "audit": report, "config": config, "warnings": res.warnings}
        repair_note = report["fail_summary"]
        if res.warnings:
            repair_note += " | warnings: " + "; ".join(res.warnings[:5])
        last = {"ok": False, "attempts": attempt, "audit": report,
                "dxf": dxf_path, "config": config, "warnings": res.warnings}

    return last or {"ok": False, "attempts": max_attempts, "error": "no result"}
```

Also update the module docstring's first line (line 1) to reflect config, not script:

```python
"""Agent: shell + params -> generate JSON config -> apply -> audit -> self-repair (<=3)
-> render PNG -> DXF + PNG + audit report. generate_fn is injected (defaults to MLX)."""
```

- [ ] **Step 4: Run to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_agent.py -q`
Expected: PASS — `test_design_success` (attempt 1, `ok` True) and `test_design_self_repairs` (attempt 2, `ok` True)

- [ ] **Step 5: Commit**

```bash
git add engine/agent.py tests/test_agent.py
git commit -m "feat(layout-ai): agent applies JSON config + surfaces warnings

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Remove dead code (`run_script`, `fp_to_script`) + guard against exec

**Files:**
- Modify: `engine/executor.py` (delete `run_script`, `_strip_fence`, `_check_banned`)
- Modify: `data/reverse_engineer.py` (delete `fp_to_script`)
- Test: `tests/test_executor.py` (delete the three `run_script` tests; add a no-exec guard), `tests/test_reverse_engineer.py` (delete the three `fp_to_script` tests)

- [ ] **Step 1: Confirm no remaining references**

Run: `source .venv/bin/activate && grep -rn "run_script\|fp_to_script\|_strip_fence\|_check_banned\b" engine data tests --include=*.py`
Expected: only the definitions in `engine/executor.py` / `data/reverse_engineer.py` and the to-be-deleted tests appear (no production caller remains after Tasks 4–5).

- [ ] **Step 2: Delete the old tests and add the no-exec guard**

In `tests/test_executor.py`: delete `test_runs_simple_script_to_dxf`, `test_banned_block_is_rejected_before_exec`, and `test_syntax_error_is_captured` (the three that call `run_script`), and remove `run_script` from the top import (`from engine.executor import apply_layout, ExecResult`). Add:

```python
def test_no_code_execution_in_executor():
    import inspect
    import engine.executor as ex
    src = inspect.getsource(ex)
    assert "exec(" not in src
    assert "compile(" not in src
```

In `tests/test_reverse_engineer.py`: delete `test_script_is_string_with_place_calls`, `test_script_skips_shell_block`, `test_script_has_zone_comments`, and remove `fp_to_script` from the import.

- [ ] **Step 3: Delete the dead production code**

In `engine/executor.py`: delete the `run_script` function, the `_strip_fence` function, and the old `_check_banned` function (the new code uses `_check_banned_ops`). Keep `ExecResult`, `_Placer`, and everything added in Task 1.

In `data/reverse_engineer.py`: delete the `fp_to_script` function. Keep `_local_bbox`, `_zone_comment`, `STORE_SCALE`, and `fp_to_config`.

- [ ] **Step 4: Run the full suite**

Run: `source .venv/bin/activate && python -m pytest -q`
Expected: PASS — full suite green, no `exec`/`compile` in the executor.

- [ ] **Step 5: Commit**

```bash
git add engine/executor.py data/reverse_engineer.py tests/test_executor.py tests/test_reverse_engineer.py
git commit -m "refactor(layout-ai): drop runtime codegen path (run_script/fp_to_script)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: End-to-end verification against the base model

**Files:** none (verification only; `run_smoke.py` already exists)

- [ ] **Step 1: Full suite once more**

Run: `source .venv/bin/activate && python -m pytest -q`
Expected: all tests PASS.

- [ ] **Step 2: Smoke test with the base model**

Run: `source .venv/bin/activate && python run_smoke.py "../fine-turning/BASE FILES/BASE 8.dxf"`
Expected: completes without a parse/`exec` `SyntaxError`. The printed `RESULT` shows the run reached the auditor — i.e. either `ok = True`, or `ok = False` with an `audit` report (a failing audit is acceptable; the base model is untrained). A hard parse error or traceback is a FAIL for this step.

- [ ] **Step 3: Record the outcome**

Note in the final summary whether the base model's config now reaches the auditor, and capture any `warnings` (e.g. truncation recovery) the run produced — these confirm graceful degradation is working.

---

## Notes for the implementer
- Run every command from `store-layout-ai/` with the venv activated (`source .venv/bin/activate`).
- The `tiny_shell` fixture (`conftest.py`) is a 6000×4000 A-WALL rectangle with one column at local (2000,0)–(2300,300); `EURO 1040 x 1175` is a real library block and places cleanly except on that column.
- Out of scope (do NOT touch): `derive_params` `target_fixtures` value, the actual MLX fine-tune, `engine/app.py`, `web/index.html`, `engine/auditor.py`, `engine/model.py`.
