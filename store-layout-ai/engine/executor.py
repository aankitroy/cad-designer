"""Execute a model-generated placer script against the bundled libraries → output DXF.
The script body runs with only `placer` (+ safe builtins) in scope. Banned blocks are
rejected before execution."""
import re
import traceback
from dataclasses import dataclass
from typing import Optional
import skilllib
from data.rules import BANNED_BLOCKS


@dataclass
class ExecResult:
    error: Optional[str]
    dxf_path: Optional[str]
    placer: Optional[object]
    doc: Optional[object]


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
