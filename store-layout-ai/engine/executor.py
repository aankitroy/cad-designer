"""Execute a model-generated placer script against the bundled libraries → output DXF.
The script body runs with only `placer` (+ safe builtins) in scope. Banned blocks are
rejected before execution."""
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


def _strip_fence(script):
    m = re.search(r"```(?:python)?\s*(.*?)```", script, re.DOTALL)
    return (m.group(1) if m else script).strip()


def _check_banned(code):
    # Only inspect block names passed to placer.place(...); ignore comments and rects,
    # so a substitution comment like `# TV 55"` is never a false positive. Exact match
    # avoids flagging legit names that merely contain a banned token (e.g. CLINIC - CABINET SINK).
    names = [n.upper() for n in re.findall(r"placer\.place\(\s*['\"]([^'\"]+)['\"]", code)]
    for b in BANNED_BLOCKS:
        if b.upper() in names:
            return f"banned block referenced: {b}"
    return None


def run_script(script, shell_path, out_path):
    code = _strip_fence(script)
    banned = _check_banned(code)
    if banned:
        return ExecResult(error=banned, dxf_path=None, placer=None, doc=None)
    try:
        doc, msp, OX, OY = skilllib.load_shell(shell_path)
        skilllib.import_library(doc)
        skilllib.import_clinic_rooms(doc)
        placer = _Placer(doc, msp, OX, OY)
        safe = {"__builtins__": {"range": range, "len": len, "min": min, "max": max,
                                 "int": int, "float": float, "round": round, "abs": abs}}
        exec(compile(code, "<layout>", "exec"), safe, {"placer": placer})
        doc.saveas(out_path)
        return ExecResult(error=None, dxf_path=out_path, placer=placer, doc=doc)
    except Exception:
        return ExecResult(error=traceback.format_exc(limit=4), dxf_path=None, placer=None, doc=None)


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


def _check_banned_ops(placements):
    names = {str(p.get("block", "")).upper() for p in placements if p.get("op") == "place"}
    for b in BANNED_BLOCKS:
        if b.upper() in names:
            return f"banned block referenced: {b}"
    return None


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
