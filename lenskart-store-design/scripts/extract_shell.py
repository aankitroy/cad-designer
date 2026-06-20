"""
Extract the STRUCTURE of any base-CAD shell, in the local frame (world - A-WALL min).

This is STEP 1 for any new store. It finds the things you must NOT overlap and the
things that drive the layout:  walls outline, COLUMNS (incl. free-standing mid-floor
ones), BEAMS, the shaft, the existing toilet, and the entry/door.

Usage:
    python scripts/extract_shell.py "/path/to/NEW SHELL.dxf"
Writes <shell>.structure.json next to nothing (prints path) and prints a readable map.

The COLUMNS and BEAMS arrays are HARD obstructions: every fixture footprint must be
audited against them (see audit.py). Fixtures may butt a face but never overlap.
"""
import sys, os, json, math
import ezdxf, ezdxf.bbox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxf_engine import load_shell, _walk


def _ent_bbox_local(e, OX, OY):
    try:
        b = ezdxf.bbox.extents([e])
    except Exception:
        return None
    if not b.has_data:
        return None
    r = (b.extmin.x - OX, b.extmin.y - OY, b.extmax.x - OX, b.extmax.y - OY)
    if any(abs(v) > 5e6 for v in r):   # parked / stray
        return None
    return r


def _merge(boxes, tol=150):
    """Union-find merge of overlapping/adjacent boxes (within tol mm) into clusters."""
    boxes = [list(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        out = []
        for b in boxes:
            placed = False
            for o in out:
                if (b[0] <= o[2] + tol and o[0] <= b[2] + tol and
                        b[1] <= o[3] + tol and o[1] <= b[3] + tol):
                    o[0], o[1] = min(o[0], b[0]), min(o[1], b[1])
                    o[2], o[3] = max(o[2], b[2]), max(o[3], b[3])
                    placed = True; changed = True; break
            if not placed:
                out.append(b)
        boxes = out
    return [tuple(round(v) for v in b) for b in boxes]


def extract_structure(path):
    doc, msp, OX, OY = load_shell(path)
    # gather flattened entities (world) with their layer
    flat = []
    for e in msp:
        if e.dxftype() == "INSERT":
            for sub in _walk(e):
                flat.append(sub)
        else:
            flat.append(e)

    def boxes_on(layer):
        out = []
        for e in flat:
            if e.dxf.layer == layer:
                r = _ent_bbox_local(e, OX, OY)
                if r and (r[2] - r[0] > 30 or r[3] - r[1] > 30):
                    out.append(r)
        return out

    awall = boxes_on("A-WALL")
    wall_bbox = None
    if awall:
        wall_bbox = (round(min(b[0] for b in awall)), round(min(b[1] for b in awall)),
                     round(max(b[2] for b in awall)), round(max(b[3] for b in awall)))

    columns = _merge(boxes_on("column"), tol=120)
    beams = _merge(boxes_on("beam"), tol=120)
    # column-hatch is usually a fill, not an obstruction; report separately, flag large ones
    colhatch = _merge(boxes_on("column hatch"), tol=120)

    # shaft / toilet via text labels
    labels = []
    for e in flat:
        if e.dxftype() in ("TEXT", "MTEXT"):
            t = (e.text if e.dxftype() == "MTEXT" else e.dxf.text)
            t = t.replace("\\P", " ")
            labels.append((t, round(e.dxf.insert.x - OX), round(e.dxf.insert.y - OY)))

    # doors / entry
    doors = []
    for e in flat:
        if e.dxf.layer in ("Door", "LENS-DOOR", "LK-DOOR", "A-Glazing") and e.dxftype() == "INSERT":
            doors.append((e.dxf.name, round(e.dxf.insert.x - OX), round(e.dxf.insert.y - OY), round(e.dxf.rotation)))
        if e.dxftype() == "ARC" and e.dxf.layer in ("Door", "LENS-DOOR", "LK-DOOR"):
            doors.append(("ARC", round(e.dxf.center.x - OX), round(e.dxf.center.y - OY), round(e.dxf.radius)))

    struct = dict(
        shell=os.path.basename(path), origin_world=[round(OX), round(OY)], wall_bbox=wall_bbox,
        columns=[list(c) for c in columns], beams=[list(b) for b in beams],
        column_hatch=[list(c) for c in colhatch],
        labels=labels, doors=doors,
    )
    return struct


def _print(struct):
    print("SHELL:", struct["shell"], " origin(world):", struct["origin_world"])
    wb = struct["wall_bbox"]
    if wb:
        print(f"A-WALL bbox (local): x[{wb[0]},{wb[2]}] y[{wb[1]},{wb[3]}]  W={wb[2]-wb[0]} H={wb[3]-wb[1]}")
    print(f"\nCOLUMNS ({len(struct['columns'])}) -- HARD obstructions, never overlap:")
    for c in struct["columns"]:
        print(f"   x[{c[0]},{c[2]}] y[{c[1]},{c[3]}]  ({c[2]-c[0]}x{c[3]-c[1]})")
    print(f"\nBEAMS ({len(struct['beams'])}) -- HARD obstructions:")
    for c in struct["beams"]:
        print(f"   x[{c[0]},{c[2]}] y[{c[1]},{c[3]}]  ({c[2]-c[0]}x{c[3]-c[1]})")
    if struct["column_hatch"]:
        print(f"\ncolumn-hatch ({len(struct['column_hatch'])}) -- usually fill, verify before trusting:")
        for c in struct["column_hatch"]:
            print(f"   x[{c[0]},{c[2]}] y[{c[1]},{c[3]}]  ({c[2]-c[0]}x{c[3]-c[1]})")
    print("\nLABELS (toilet/shaft/etc.):")
    for t, x, y in struct["labels"]:
        print(f"   {t!r} @ ({x},{y})")
    print("\nDOORS / entry:")
    for d in struct["doors"]:
        print("  ", d)
    print("\n>> Treat every COLUMN and BEAM as a no-overlap zone. Find the SHAFT (a column-")
    print(">> like rect, often labelled) and the EXISTING TOILET (label + wall enclosure);")
    print(">> reuse the toilet and keep its door swing + approach clear.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python extract_shell.py <shell.dxf>"); sys.exit(1)
    s = extract_structure(sys.argv[1])
    _print(s)
    # write to cwd (input folder may be read-only); allow override as 2nd arg
    out = sys.argv[2] if len(sys.argv) > 2 else \
        os.path.join(os.getcwd(), os.path.splitext(os.path.basename(sys.argv[1]))[0] + ".structure.json")
    try:
        with open(out, "w") as f:
            json.dump(s, f, indent=2)
        print("\nwrote", out)
    except OSError as e:
        print("\n(could not write json:", e, "- structure printed above)")
