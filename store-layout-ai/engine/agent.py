"""Agent: shell + params -> generate JSON config -> apply -> audit -> self-repair (<=3)
-> render PNG -> DXF + PNG + audit report. generate_fn is injected (defaults to MLX)."""
import json
import os
import shutil
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


def _write_artifacts(attempt_dir, config, res, report):
    """Persist the raw model output + a meta summary for one attempt. The DXF/PNG are
    written by the build/render steps; this records everything else so a rejected attempt
    is fully inspectable on disk."""
    with open(os.path.join(attempt_dir, "config.json"), "w") as f:
        f.write(config if isinstance(config, str) else json.dumps(config, indent=2))
    meta = {"error": res.error, "warnings": res.warnings, "audit": report,
            "dxf": res.dxf_path}
    with open(os.path.join(attempt_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2, default=str)


def _promote(out_dir, result):
    """Copy the chosen attempt's DXF/PNG to the job root as the canonical result, so the
    download endpoints find a stable path while per-attempt files stay in attempt_N/."""
    for key, name in (("dxf", "layout.dxf"), ("png", "layout.png")):
        src = result.get(key)
        if src and os.path.isfile(src):
            dst = os.path.join(out_dir, name)
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copyfile(src, dst)
            result[key] = dst
    return result


def design(shell_path, params, out_dir, generate_fn=None, max_attempts=3):
    os.makedirs(out_dir, exist_ok=True)
    generate_fn = generate_fn or _default_generate
    struct = skilllib.extract_structure(shell_path)
    repair_note, last = None, None

    for attempt in range(1, max_attempts + 1):
        user = build_user_prompt(shell_path, params, repair_note)
        config = generate_fn(SYSTEM_PROMPT, user)
        attempt_dir = os.path.join(out_dir, f"attempt_{attempt}")
        os.makedirs(attempt_dir, exist_ok=True)
        dxf_path = os.path.join(attempt_dir, "layout.dxf")
        png_path = os.path.join(attempt_dir, "layout.png")

        # Always build best-effort so the attempt is inspectable even when rejected:
        # banned/unplaceable blocks become placeholder markers, and the DXF/PNG are
        # always written when a doc could be built.
        res = apply_layout(config, shell_path, dxf_path, best_effort=True)
        if res.doc is not None:
            try:
                skilllib.render_png(res.doc, png_path)
            except Exception as e:  # noqa: BLE001 - render is best-effort for inspection
                res.warnings.append(f"render failed: {str(e)[:80]}")
        png = png_path if (res.doc is not None and os.path.isfile(png_path)) else None

        report = None
        if res.error is None and res.placer is not None:
            report = structured_audit(res.placer, struct,
                                      target_count=params.get("target_fixtures"))
        _write_artifacts(attempt_dir, config, res, report)

        if res.error:
            repair_note = f"Config error: {res.error[:300]}"
            last = {"ok": False, "attempts": attempt, "error": res.error, "config": config,
                    "dir": attempt_dir, "dxf": res.dxf_path, "png": png, "warnings": res.warnings}
            continue
        if report["passed"]:
            return _promote(out_dir, {"ok": True, "attempts": attempt, "dir": attempt_dir,
                                      "dxf": dxf_path, "png": png, "audit": report,
                                      "config": config, "warnings": res.warnings})
        repair_note = report["fail_summary"]
        if res.warnings:
            repair_note += " | warnings: " + "; ".join(res.warnings[:5])
        last = {"ok": False, "attempts": attempt, "audit": report, "dir": attempt_dir,
                "dxf": dxf_path, "png": png, "config": config, "warnings": res.warnings}

    return _promote(out_dir, last) if last else {"ok": False, "attempts": max_attempts,
                                                 "error": "no result"}
