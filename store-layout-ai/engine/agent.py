"""Agent: shell + params -> generate JSON config -> apply -> audit -> self-repair (<=3)
-> render PNG -> DXF + PNG + audit report. generate_fn is injected (defaults to MLX)."""
import json
import os
import skilllib
from data.rules import SYSTEM_PROMPT
from engine.executor import apply_layout
from engine.auditor import structured_audit


def _default_generate(system, user):
    from engine.model import generate
    return generate(system, user)


def build_user_prompt(shell_path, params, repair_note=None):
    struct = skilllib.extract_structure(shell_path)
    msg = f"SHELL:\n{json.dumps(struct)}\n\nPARAMS:\n{json.dumps(params)}"
    if repair_note:
        msg += f"\n\nPREVIOUS ATTEMPT FAILED:\n{repair_note}\nFix these and regenerate."
    return msg


def design(shell_path, params, out_dir, generate_fn=None, max_attempts=3):
    os.makedirs(out_dir, exist_ok=True)
    generate_fn = generate_fn or _default_generate
    struct = skilllib.extract_structure(shell_path)
    repair_note, last = None, None

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
