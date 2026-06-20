"""Reverse-engineer a finished FP DXF into a flat, annotated placer.* script in LOCAL
coordinates. One place() per top-level INSERT (positioned by its bbox-min, matching how
Placer.place works), rect() substitutions for retired blocks, placer.fire() for
extinguishers, skip for shell blocks. Anonymous blocks fall back to a labelled rect;
store-scale anonymous blocks (outlines/hatches, not fixtures) are skipped."""
import ezdxf, ezdxf.bbox
import skilllib
from data.block_map import classify

# Anonymous blocks bigger than this in either dimension are store-scale (outline/hatch),
# not a fixture → skip rather than draw a giant rect.
STORE_SCALE = 4000


def _local_bbox(ref, OX, OY):
    bb = ezdxf.bbox.extents([ref])
    if not bb.has_data:
        return None
    return (round(bb.extmin.x - OX), round(bb.extmin.y - OY),
            round(bb.extmax.x - OX), round(bb.extmax.y - OY))


def _zone_comment(y0, wall_h):
    """Cheap zoning heuristic for an annotation comment from local y position."""
    if y0 > wall_h * 0.66:
        return "back zone (clinics / BOH)"
    if y0 < wall_h * 0.15:
        return "front (entry / glazing)"
    return "mid retail"


def fp_to_script(fp_path):
    doc, msp, OX, OY = skilllib.load_shell(fp_path)
    struct = skilllib.extract_structure(fp_path)
    wb = struct.get("wall_bbox") or (0, 0, 1, 1)
    wall_h = max(1, wb[3] - wb[1])

    lines = ["# Reverse-engineered layout (LOCAL mm).  placer.place positions by bbox-min."]
    placed = 0
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
            lines.append(f"# {target} — {_zone_comment(y0, wall_h)}")
            lines.append(f"placer.place({target!r}, x={x0}, y={y0}, rot={rot})")
            placed += 1
        elif kind == "fire":
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            lines.append(f"placer.fire({cx}, {cy})")
        elif kind == "substitute":
            lines.append(f"# {target['label']} (substituted rect)")
            lines.append(f"placer.rect({x0}, {y0}, {x1}, {y1}, layer={target['layer']!r})")
        else:  # unmapped anonymous block
            if (x1 - x0) > STORE_SCALE or (y1 - y0) > STORE_SCALE:
                continue  # store-scale outline/hatch, not a fixture
            lines.append(f"# anonymous {name} → rect fallback")
            lines.append(f"placer.rect({x0}, {y0}, {x1}, {y1}, layer='LK-FURNITURE')")
    if placed == 0:
        raise ValueError(f"no placeable inserts in {fp_path}")
    return "```python\n" + "\n".join(lines) + "\n```"
