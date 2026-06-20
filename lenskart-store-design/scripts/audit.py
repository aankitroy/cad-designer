"""
Clearance / collision / count audit for a built layout.

Pass it the Placer (after placing everything) and the structure dict from
extract_shell.py. It reports the things sign-off depends on:

  1. fixture vs COLUMN/BEAM/SHAFT/TOILET overlaps  -> MUST be zero
  2. fixture vs fixture overlaps (excluding TVs, which sit above euros) -> MUST be zero
  3. retail display-fixture count vs target (approximate; over preferred)

Aisle widths between specific fixtures are easy to compute directly from
Placer.placed coordinates in the build script; this module gives the hard checks.
"""

def _ov(a, b, tol=5):
    return (min(a[2], b[2]) - max(a[0], b[0])) > tol and (min(a[3], b[3]) - max(a[1], b[1])) > tol


def audit(placer, structure, target_count=None, extra_obstructions=None):
    obst = {}
    for i, c in enumerate(structure.get("columns", [])):
        obst[f"column#{i}"] = tuple(c)
    for i, c in enumerate(structure.get("beams", [])):
        obst[f"beam#{i}"] = tuple(c)
    if extra_obstructions:
        obst.update(extra_obstructions)   # e.g. {"SHAFT":(...), "TOILET":(...)}

    placed = placer.placed
    report = {"obstruction_hits": [], "fixture_overlaps": [], "retail_count": placer.retail_count(),
              "target_count": target_count}

    for p in placed:
        box = (p["x0"], p["y0"], p["x1"], p["y1"])
        for on, ob in obst.items():
            if _ov(box, ob):
                report["obstruction_hits"].append((p["label"], [round(v) for v in box], on))

    aud = [p for p in placed if p["audit"] and p["name"] != "55INCH" and "TV" not in p["name"].upper()]
    for i in range(len(aud)):
        for j in range(i + 1, len(aud)):
            a, b = aud[i], aud[j]
            ba = (a["x0"], a["y0"], a["x1"], a["y1"]); bb = (b["x0"], b["y0"], b["x1"], b["y1"])
            if _ov(ba, bb):
                report["fixture_overlaps"].append((a["label"], b["label"]))
    return report


def print_report(report):
    print("=" * 60)
    print("CLEARANCE / COLLISION AUDIT")
    print("=" * 60)
    oh = report["obstruction_hits"]
    print(f"\n[1] Fixture vs column/beam/shaft/toilet overlaps: {len(oh)}  (MUST be 0)")
    for lbl, box, on in oh:
        print(f"    HIT  {lbl:24s} {box}  x {on}")
    fo = report["fixture_overlaps"]
    print(f"\n[2] Fixture vs fixture overlaps: {len(fo)}  (MUST be 0)")
    for a, b in fo:
        print(f"    OVL  {a}  x  {b}")
    print(f"\n[3] Retail display fixtures: {report['retail_count']}", end="")
    if report["target_count"]:
        print(f"   (target ~{report['target_count']}; approximate, over preferred)")
    else:
        print()
    ok = (len(oh) == 0 and len(fo) == 0)
    print("\nRESULT:", "PASS (no overlaps)" if ok else "FAIL - resolve overlaps above")
    return ok
