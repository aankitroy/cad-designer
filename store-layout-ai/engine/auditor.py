"""Structured audit wrapper. Delegates the hard geometric checks to the skill's audit.py
(no logic fork) and adds circulation/access checks (walk-around, door swing, washroom
approach) the prose rules require but the original auditor does not enforce. Returns a
machine-readable result the self-repair loop can consume."""
import skilllib

MAJOR_AREA = 400_000      # mm^2 — euros/clinics/billing count as circulation obstacles
MIN_AISLE = 900           # mm — below this two facing majors pinch circulation
TRAP_LOW = 250            # mm — below this is treated as intentional butting, not an aisle
DOOR_CLEAR = 900          # mm — default swing/approach box side for non-arc doors
WASHROOM_CLEAR = 1000     # mm — clear approach zone around the toilet


def _ov(a, b, tol=5):
    return (min(a[2], b[2]) - max(a[0], b[0])) > tol and (min(a[3], b[3]) - max(a[1], b[1])) > tol


def _box(p):
    return (p["x0"], p["y0"], p["x1"], p["y1"])


def _area(b):
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def _gap(a, b):
    """If boxes a,b face each other (overlap on one axis, separated on the other),
    return the separation distance in mm; else None."""
    x_ov = min(a[2], b[2]) - max(a[0], b[0])
    y_ov = min(a[3], b[3]) - max(a[1], b[1])
    if x_ov > 0 and y_ov < 0:
        return -y_ov
    if y_ov > 0 and x_ov < 0:
        return -x_ov
    return None


def check_walk_around(placed):
    """WARN on pinch points: two major fixtures facing each other with a gap too tight
    to walk (rules §5/§14/§15.6). Heuristic → WARN, not FAIL, to avoid blocking the loop."""
    majors = [(p["label"], _box(p)) for p in placed if _area(_box(p)) > MAJOR_AREA]
    tight = []
    for i in range(len(majors)):
        for j in range(i + 1, len(majors)):
            g = _gap(majors[i][1], majors[j][1])
            if g is not None and TRAP_LOW < g < MIN_AISLE:
                tight.append((majors[i][0], majors[j][0], round(g)))
    return {"check": "walk_around",
            "status": "WARN" if tight else "PASS",
            "detail": "; ".join(f"{a}~{b}={d}mm" for a, b, d in tight[:6])}


def _door_zones(structure):
    """Clearance zone per door from structure['doors']: ARC entries carry a swing radius;
    INSERT doors use a default box centred on the insert point."""
    zones = []
    for d in structure.get("doors", []):
        if not d:
            continue
        if d[0] == "ARC":
            _, cx, cy, r = d
            zones.append((f"door@({cx},{cy})", (cx - r, cy - r, cx + r, cy + r)))
        else:
            name, x, y = d[0], d[1], d[2]
            h = DOOR_CLEAR / 2
            zones.append((f"door:{name}", (x - h, y - h, x + h, y + h)))
    return zones


def check_door_access(placed, structure):
    """FAIL if any fixture overlaps a door's swing/approach zone (entry/toilet/BOH)."""
    hits = []
    for label, zone in _door_zones(structure):
        for p in placed:
            if _ov(_box(p), zone):
                hits.append((p["label"], label))
    return {"check": "door_access",
            "status": "FAIL" if hits else "PASS",
            "detail": "; ".join(f"{f} blocks {d}" for f, d in hits[:6])}


def _toilet_point(structure):
    for entry in structure.get("labels", []):
        t = entry[0].upper()
        if "TOILET" in t or "WC" in t or "WASHROOM" in t:
            return (entry[1], entry[2])
    return None


def check_washroom_access(placed, structure):
    """FAIL if the toilet's approach zone is blocked; N/A if no toilet label found."""
    pt = _toilet_point(structure)
    if pt is None:
        return {"check": "washroom_access", "status": "N/A", "detail": "no toilet label found"}
    h = WASHROOM_CLEAR / 2
    zone = (pt[0] - h, pt[1] - h, pt[0] + h, pt[1] + h)
    blockers = [p["label"] for p in placed if _ov(_box(p), zone)]
    return {"check": "washroom_access",
            "status": "FAIL" if blockers else "PASS",
            "detail": "" if not blockers else "blocked by " + ", ".join(blockers[:5])}


def structured_audit(placer, structure, target_count=None, extra_obstructions=None):
    report = skilllib.audit(placer, structure, target_count=target_count,
                            extra_obstructions=extra_obstructions)
    checks = []

    oh = report["obstruction_hits"]
    checks.append({"check": "column_beam_overlap",
                   "status": "PASS" if not oh else "FAIL",
                   "detail": "" if not oh else "; ".join(f"{l} x {o}" for l, _, o in oh)})

    fo = report["fixture_overlaps"]
    checks.append({"check": "fixture_overlap",
                   "status": "PASS" if not fo else "FAIL",
                   "detail": "" if not fo else "; ".join(f"{a} x {b}" for a, b in fo)})

    checks.append(check_walk_around(placer.placed))
    checks.append(check_door_access(placer.placed, structure))
    checks.append(check_washroom_access(placer.placed, structure))

    if target_count:
        rc = report["retail_count"]
        ok = rc >= target_count - 3   # approximate, under by ≤3 acceptable (rule 4)
        checks.append({"check": "fixture_count",
                       "status": "PASS" if ok else "WARN",
                       "detail": f"{rc} vs target ~{target_count}"})

    fires = sum(1 for p in placer.placed if p["name"] == "Fire Extinguisher") \
        + sum(1 for c in placer.msp.query("CIRCLE") if c.dxf.layer == "F-FIRE EXTINGUISHER")
    checks.append({"check": "fire_extinguishers",
                   "status": "PASS" if fires >= 3 else "WARN",
                   "detail": f"{fires} found (need >=3)"})

    passed = all(c["status"] != "FAIL" for c in checks)
    return {"checks": checks, "passed": passed,
            "fail_summary": "; ".join(f"{c['check']}: {c['detail']}"
                                      for c in checks if c["status"] == "FAIL")}
