"""
Canonical clinic arrangements (from 2/3 CLINIC LIBRARY.dxf).

USE THESE DIRECTLY. Do not invent clinic positions unless none of these physically
fit the shell's back zone. Each room is a pre-made block:
    SINK clinic = A$C15b5f610  (sink+storage; 2600x1700)
    RO   clinic = A$Cc304dd19  (remote optometry/phoropter; 2600x1700)

Rooms are stored by CENTRE (relative to the arrangement's min corner) + rotation.
place_arrangement() imports the room blocks and drops the whole arrangement with its
bbox-min at a target, optionally rotated 0/90/180/270 to face the openings toward the
corridor and away from the toilet door.

Footprints:  landscape (rot 0/180) = 2600 x 1700;  portrait (rot 90/270) = 1700 x 2600.
Each room opens (curtain) on a LONG side -- orient so that side faces a clear corridor.
"""
import os, sys, math
import ezdxf, ezdxf.bbox
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxf_engine import import_clinic_rooms, SINK_ROOM_BLOCK, RO_ROOM_BLOCK

# rooms: (role, centre_x, centre_y, rotation)  -- centres relative to arrangement min corner
ARRANGEMENTS = {
    # ---- TWO clinic (1 SINK + 1 RO) ----
    "2A": {"desc": "twin landscape, side-by-side; both open on long bottom side; ~5100x1700; wide+shallow back",
           "footprint": (5100, 1700),
           "rooms": [("SINK", 1300, 850, 0), ("RO", 3800, 850, 0)]},
    "2B": {"desc": "L-shape: SINK landscape + RO portrait wrapping a corner; ~4200x2600",
           "footprint": (4200, 2600),
           "rooms": [("SINK", 1300, 1750, 0), ("RO", 3350, 1300, 270)]},
    "2C": {"desc": "twin portrait + 750 central corridor, rooms open toward each other; ~4150x2600; narrow+deep back",
           "footprint": (4150, 2600),
           "rooms": [("SINK", 850, 1300, 90), ("RO", 3300, 1300, 270)]},
    # ---- THREE clinic ----
    "3A": {"desc": "triple landscape row (SINK+SINK+RO), all open bottom; ~7600x1700; wide+shallow back",
           "footprint": (7600, 1700),
           "rooms": [("SINK", 1300, 850, 0), ("SINK", 3800, 850, 0), ("RO", 6300, 850, 0)]},
    "3B": {"desc": "portrait-landscape-portrait cluster (RO+SINK+RO), 750 corridors; ~5800x2600",
           "footprint": (5800, 2600),
           "rooms": [("RO", 850, 1300, 90), ("SINK", 2900, 1750, 0), ("RO", 4950, 1300, 270)]},
    "3C": {"desc": "mixed row (RO portrait + SINK + RO landscape); ~6700x2600",
           "footprint": (6700, 2600),
           "rooms": [("RO", 850, 1300, 90), ("SINK", 2900, 1750, 0), ("RO", 5400, 1750, 0)]},
}


def _rot_pt(x, y, deg):
    r = math.radians(deg); c, s = math.cos(r), math.sin(r)
    return (x * c - y * s, x * s + y * c)


def _clean_bbox(ref):
    """bbox of a clinic-room INSERT excluding stray DIMENSION/TEXT (the RO block carries one)."""
    xs, ys = [], []
    for v in ref.virtual_entities():
        if v.dxftype() in ("DIMENSION", "TEXT", "MTEXT"):
            continue
        try:
            b = ezdxf.bbox.extents([v])
        except Exception:
            continue
        if b.has_data and abs(b.extmin.x) < 1e7:
            xs += [b.extmin.x, b.extmax.x]; ys += [b.extmin.y, b.extmax.y]
    return (min(xs), min(ys), max(xs), max(ys))


def place_arrangement(placer, key, ox, oy, arr_rot=0, layer="LENS-PARTITION"):
    """Place clinic arrangement `key` with its bbox-min at LOCAL (ox,oy), rotated by arr_rot (0/90/180/270).
    Returns list of placed room rects [(role,x0,y0,x1,y1), ...] (added to placer.placed for the audit)."""
    import_clinic_rooms(placer.doc)
    rooms = ARRANGEMENTS[key]["rooms"]
    # rotate centres, derive final footprint per room
    tmp = []
    for role, cx, cy, rot in rooms:
        rcx, rcy = _rot_pt(cx, cy, arr_rot)
        frot = (rot + arr_rot) % 360
        w, h = (2600, 1700) if frot % 180 == 0 else (1700, 2600)
        tmp.append((role, rcx, rcy, frot, w, h))
    minx = min(c[1] - c[4] / 2 for c in tmp)
    miny = min(c[2] - c[5] / 2 for c in tmp)
    out = []
    for role, rcx, rcy, frot, w, h in tmp:
        cx = ox + (rcx - minx); cy = oy + (rcy - miny)
        block = SINK_ROOM_BLOCK if role == "SINK" else RO_ROOM_BLOCK
        ref = placer.msp.add_blockref(block, (placer.OX, placer.OY),
                                      dxfattribs={"rotation": frot, "layer": layer})
        bb = _clean_bbox(ref)
        ccx, ccy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        ref.dxf.insert = (ref.dxf.insert.x + (placer.OX + cx) - ccx,
                          ref.dxf.insert.y + (placer.OY + cy) - ccy)
        x0, y0 = cx - w / 2, cy - h / 2
        rec = dict(name=f"CLINIC-{role}", label=f"CLINIC {role}", x0=x0, y0=y0, x1=x0 + w, y1=y0 + h,
                   retail=False, audit=True)
        placer.placed.append(rec)
        placer.txt(f"CLINIC {role}", x0 + 80, y0 + h - 250, 110, "LK-TEXT")
        out.append((role, round(x0), round(y0), round(x0 + w), round(y0 + h)))
    return out


def list_arrangements():
    for k, v in ARRANGEMENTS.items():
        print(f"{k}: {v['desc']}  (footprint {v['footprint'][0]}x{v['footprint'][1]})")


if __name__ == "__main__":
    list_arrangements()
