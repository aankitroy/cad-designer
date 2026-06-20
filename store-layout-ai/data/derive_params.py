"""Derive store params from a finished FP DXF so training params match what the web UI
will later supply. Fixture count = wall+floor DISPLAY units only (rule 4)."""
import skilllib
from data.block_map import classify, CLINIC_ROOMS

# Wall+floor display fixture name fragments (rule 4: NOT billing/greeter/clinic/BOH/TV).
DISPLAY_HINTS = ("JJ ", "VC ", "CLENS", "EURO", "AWEC", "AWOEC", "BLUE ZERO",
                 "HALF EURO", "LENS SELECTION")


def _count_display(names):
    hints = tuple(h.upper() for h in DISPLAY_HINTS)
    return sum(1 for n in names if any(h in n.upper() for h in hints))


def _clinic_count(names):
    """FPs use per-file-hashed clinic room blocks, so count canonical rooms first; else
    estimate from clinic chairs (one per clinic). Clamp to the valid protos (2/3/4)."""
    rooms = sum(1 for n in names if n in CLINIC_ROOMS)
    if rooms in (2, 3, 4):
        return rooms
    chairs = sum(1 for n in names if "CHAIR UNIT" in n.upper())
    return min(4, max(2, chairs)) if chairs else 2


def derive_params(fp_path):
    doc, msp, OX, OY = skilllib.load_shell(fp_path)
    struct = skilllib.extract_structure(fp_path)
    wb = struct.get("wall_bbox") or (0, 0, 1, 1)
    names = [e.dxf.name for e in msp.query("INSERT")]

    target_fixtures = max(1, _count_display(names))

    # entry side: door nearest a wall edge; default west (skill convention).
    entry_side = "west"
    doors = struct.get("doors") or []
    if doors:
        dx = doors[0][1]
        width = max(1, wb[2] - wb[0])
        entry_side = "west" if dx < width / 2 else "east"

    # premium side: the longer side wall opposite the value wall; default south.
    premium_side = "south"
    return {"clinic_count": _clinic_count(names), "target_fixtures": target_fixtures,
            "entry_side": entry_side, "premium_side": premium_side}
