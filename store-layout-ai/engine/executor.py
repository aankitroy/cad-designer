"""Apply a model-generated JSON layout config against the bundled libraries → output DXF.
The config is parsed, validated, and dispatched to the Placer API — no code execution.
Banned blocks are rejected before placement; malformed entries are skipped, not fatal."""
import json
import re
import traceback
from dataclasses import dataclass, field
from typing import Optional
import skilllib
from data.rules import BANNED_BLOCKS


@dataclass
class ExecResult:
    error: Optional[str]
    dxf_path: Optional[str]
    placer: Optional[object]
    doc: Optional[object]
    warnings: list = field(default_factory=list)


class _Placer(skilllib.Placer):
    """Placer that accepts the friendly x=/y= keyword convention used in generated
    scripts (the base engine uses positional tx/ty). Everything else is inherited."""
    def place(self, name, x=None, y=None, rot=0, tx=None, ty=None, **kw):
        if tx is None:
            tx = x
        if ty is None:
            ty = y
        return super().place(name, tx, ty, rot=rot, **kw)


_REQUIRED = {
    "place": ("block", "x", "y"),
    "rect": ("x0", "y0", "x1", "y1", "layer"),
    "fire": ("x", "y"),
}

# Best-effort inspection: blocks that can't actually be placed (banned or not in the
# library) are drawn as a labelled marker box so the model's spatial intent is still
# visible in the DXF/PNG, even though the layout is rejected.
PLACEHOLDER_LAYER = "LK-REJECTED"
PLACEHOLDER_W, PLACEHOLDER_H = 800, 400


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


def _placeholder(placer, p, reason, warnings):
    """Draw a labelled marker box at the op's intended position so a rejected/unplaceable
    block still shows up in the render. Never raises into the caller."""
    try:
        x, y = int(p.get("x", 0)), int(p.get("y", 0))
        placer.rect(x, y, x + PLACEHOLDER_W, y + PLACEHOLDER_H, layer=PLACEHOLDER_LAYER)
        placer.txt(f"?{p.get('block', p.get('op', '?'))}", x + 20, y + PLACEHOLDER_H + 40,
                   90, layer=PLACEHOLDER_LAYER)
        warnings.append(f"placeholder for {p.get('block', p.get('op'))} @({x},{y}): {reason[:60]}")
    except Exception as e:  # noqa: BLE001 - placeholder is best-effort, must not abort the build
        warnings.append(f"placeholder failed: {str(e)[:60]}")


def _dispatch(placer, p):
    op = p["op"]
    if op == "place":
        kw = {k: p[k] for k in ("layer", "label") if k in p}
        placer.place(p["block"], x=int(p["x"]), y=int(p["y"]), rot=int(p.get("rot", 0)), **kw)
    elif op == "rect":
        placer.rect(int(p["x0"]), int(p["y0"]), int(p["x1"]), int(p["y1"]), layer=p["layer"])
    elif op == "fire":
        placer.fire(int(p["x"]), int(p["y"]))


def _check_banned_ops(placements):
    names = {str(p.get("block", "")).upper() for p in placements if p.get("op") == "place"}
    for b in BANNED_BLOCKS:
        if b.upper() in names:
            return f"banned block referenced: {b}"
    return None


def apply_layout(config_text, shell_path, out_path, best_effort=False):
    """Parse a JSON layout config and build the DXF deterministically (no exec).
    Malformed entries are skipped (recorded in warnings); only a banned block or an
    empty/garbled config is a hard error.

    best_effort=True: build and save the DXF anyway so a rejected layout can be
    inspected. Banned/unplaceable blocks become labelled placeholder markers; the
    strict rejection reason is still reported in `.error` (with `.doc`/`.placer`
    populated), so callers can both flag the failure and open the result."""
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
    if not valid and not best_effort:
        return ExecResult(error="no valid placements in config", dxf_path=None,
                          placer=None, doc=None, warnings=warnings)
    banned = _check_banned_ops(valid)
    if banned and not best_effort:
        return ExecResult(error=banned, dxf_path=None, placer=None, doc=None, warnings=warnings)
    banned_names = {b.upper() for b in BANNED_BLOCKS}
    try:
        doc, msp, OX, OY = skilllib.load_shell(shell_path)
        skilllib.import_library(doc)
        skilllib.import_clinic_rooms(doc)
        placer = _Placer(doc, msp, OX, OY)
        for p in valid:
            if best_effort and p.get("op") == "place" \
                    and str(p.get("block", "")).upper() in banned_names:
                _placeholder(placer, p, "banned block", warnings)
                continue
            try:
                _dispatch(placer, p)
            except Exception as e:
                warnings.append(f"op {p.get('op')} failed: {str(e)[:80]}")
                if best_effort:
                    _placeholder(placer, p, str(e), warnings)
        doc.saveas(out_path)
        error = banned if (banned and best_effort) else None
        return ExecResult(error=error, dxf_path=out_path, placer=placer, doc=doc, warnings=warnings)
    except Exception:
        return ExecResult(error=traceback.format_exc(limit=4), dxf_path=None,
                          placer=None, doc=None, warnings=warnings)
