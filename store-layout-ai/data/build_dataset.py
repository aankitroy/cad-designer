"""Assemble JSONL training data from the 12 shell→FP pairs, validating each by round-trip
(execute the generated script → audit → confirm it runs clean) before inclusion."""
import json
import os
import re
import skilllib
from data.rules import SYSTEM_PROMPT
from data.reverse_engineer import fp_to_config
from data.derive_params import derive_params
from data.block_map import coverage
from engine.executor import apply_layout
import ezdxf

DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def discover_pairs():
    """Return [(shell_path, fp_path)] for every BASE N that has both files."""
    base = skilllib.BASE_FILES
    files = os.listdir(base)
    pairs = []
    for f in files:
        if not f.endswith(".dxf") or "FP" not in f:
            continue
        n = re.search(r"BASE\s+(\d+)", f)
        if not n:
            continue
        shell = next((g for g in files if re.match(rf"BASE\s+{n.group(1)}\.dxf$", g)), None)
        if shell:
            pairs.append((os.path.join(base, shell), os.path.join(base, f)))
    return sorted(pairs)


def build_record(shell_path, fp_path):
    params = derive_params(fp_path)
    struct = skilllib.extract_structure(shell_path)
    # Localize the FP against its OWN A-WALL min. Shell and FP carry identical wall
    # geometry but sit at different world coords, so each file's local frame (0-based
    # from its own A-WALL min) is the SAME frame — using the FP's own origin lands the
    # furniture inside the shared wall bbox.
    user = f"SHELL:\n{json.dumps(struct)}\n\nPARAMS:\n{json.dumps(params)}"
    assistant = json.dumps(fp_to_config(fp_path))
    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def roundtrip_ok(rec, shell_path, out_path):
    config = rec["messages"][2]["content"]
    res = apply_layout(config, shell_path, out_path)
    if res.error:
        return False, res.error
    try:
        ezdxf.readfile(out_path)
    except Exception as e:
        return False, f"DXF did not round-trip: {e}"
    struct = skilllib.extract_structure(shell_path)
    # most fixtures must land inside the wall bbox (catches coordinate-frame errors that
    # an obstruction-only check would silently pass when furniture is shifted out of bounds)
    wb = struct.get("wall_bbox")
    if wb and res.placer.placed:
        m = 500  # mm margin (a fixture may butt/slightly exceed a wall face)
        inside = sum(1 for p in res.placer.placed
                     if p["x0"] >= wb[0] - m and p["x1"] <= wb[2] + m
                     and p["y0"] >= wb[1] - m and p["y1"] <= wb[3] + m)
        frac = inside / len(res.placer.placed)
        if frac < 0.8:
            return False, f"only {inside}/{len(res.placer.placed)} fixtures inside wall bbox"
    report = skilllib.audit(res.placer, struct)
    # Columns are floor-to-ceiling (hard); beams are overhead (BOB >= 2500) so wall/low
    # fixtures legitimately pass under them — don't reject the expert layout for those.
    col_hits = [h for h in report["obstruction_hits"] if h[2].startswith("column")]
    if col_hits:
        return False, f"{len(col_hits)} column overlaps"
    return True, "ok"


def main():
    pairs = discover_pairs()
    records, skipped, allnames = [], [], set()
    for shell, fp in pairs:
        fp_doc = ezdxf.readfile(fp)
        allnames |= {e.dxf.name for e in fp_doc.modelspace().query("INSERT")}
        try:
            rec = build_record(shell, fp)
            ok, detail = roundtrip_ok(rec, shell, os.path.join(DATA_DIR, "_rt.dxf"))
        except Exception as e:
            ok, detail, rec = False, f"{type(e).__name__}: {e}", None
        (records if ok else skipped).append((os.path.basename(fp), rec, detail))
        print(("OK " if ok else "SKIP ") + os.path.basename(fp) + ("" if ok else f" :: {detail}"))

    # split ~80/20 (hold out the last as validation; tiny set)
    valid_n = max(1, len(records) // 6)
    train = records[:-valid_n] or records
    valid = records[-valid_n:]
    with open(os.path.join(DATA_DIR, "train.jsonl"), "w") as f:
        for _, rec, _ in train:
            f.write(json.dumps(rec) + "\n")
    with open(os.path.join(DATA_DIR, "valid.jsonl"), "w") as f:
        for _, rec, _ in valid:
            f.write(json.dumps(rec) + "\n")

    cov = coverage(sorted(allnames))
    with open(os.path.join(DATA_DIR, "coverage_report.md"), "w") as f:
        f.write("# Block coverage\n\n")
        for kind, items in cov.items():
            f.write(f"## {kind} ({len(items)})\n" + "\n".join(f"- {i}" for i in sorted(items)) + "\n\n")
        f.write(f"# Round-trip\n\nincluded={len(records)} skipped={len(skipped)}\n")
        for name, _, detail in skipped:
            f.write(f"- SKIP {name}: {detail}\n")
    rt = os.path.join(DATA_DIR, "_rt.dxf")
    if os.path.exists(rt):
        os.remove(rt)
    print(f"\nwrote train={len(train)} valid={len(valid)}; unmapped blocks: {cov['unmapped']}")


if __name__ == "__main__":
    main()
