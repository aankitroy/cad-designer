"""
Lenskart store-layout engine (ezdxf).  Reusable across any base-CAD shell.

Core helpers:
  - load_shell(path)         -> (doc, msp, OX, OY)   local frame = world - (A-WALL min)
  - import_library(doc)      -> imports every block from assets/BASE LIBRARY.dxf
  - import_clinic_rooms(doc) -> imports the SINK + RO clinic room blocks
  - Placer                   -> place()/wall_run()/rect()/line()/arc()/fire()/txt(), tracks placed fixtures
  - render_png(doc, out)     -> dark-background PNG preview

Units are millimetres.  Work in LOCAL coords (x east of A-WALL min, y north of it):
the Placer converts local->world automatically by adding (OX, OY).

Conventions for the shells we use: entrances are typically on the WEST (-x / left);
+y = toward the back/north wall.  Confirm per shell with extract_shell.py.
"""
import os, math
import ezdxf, ezdxf.bbox
from ezdxf.addons import importer as _importer

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
BASE_LIBRARY = os.path.join(ASSETS, "BASE LIBRARY.dxf")
CLINIC_2_LIB = os.path.join(ASSETS, "2 CLINIC LIBRARY.dxf")
CLINIC_3_LIB = os.path.join(ASSETS, "3 CLINIC LIBRARY.dxf")

SINK_ROOM_BLOCK = "A$C15b5f610"   # SINK clinic room, footprint 2600 x 1700
RO_ROOM_BLOCK   = "A$Cc304dd19"   # RO clinic room,   footprint 2600 x 1700 (carries a stray DIMENSION - ignore)

# Layers we draw on (created if absent). Colours are AutoCAD ACI.
LAYERS = [
    ("LK-FF&E WALL", 3), ("LK-FF&E FLOOR", 4), ("LK-MIRROR", 6), ("LK-FURNITURE", 5),
    ("LENS-FURNITURE", 30), ("LK-TV SCREEN", 1), ("LK-IT", 2), ("LK-EQPMT", 2),
    ("LENS-CURTAIN", 6), ("LENS-PARTITION", 8), ("F-FIRE EXTINGUISHER", 1), ("LK-TEXT", 7),
    ("LENS-DOOR-NEW", 4), ("LK-TILES FINISH", 150), ("LK-FLUTED FINISH", 40), ("LK-PAINT FINISH", 250),
]


def _walk(insert):
    """Yield all non-INSERT entities reachable through an INSERT (recursively flattened to world coords)."""
    for e in insert.virtual_entities():
        if e.dxftype() == "INSERT":
            yield from _walk(e)
        else:
            yield e


def _awall_points(msp):
    """Collect A-WALL points in world coords, flattening any shell block INSERTs."""
    xs, ys = [], []
    def consume(e):
        t = e.dxftype()
        if t == "LINE":
            xs.extend([e.dxf.start.x, e.dxf.end.x]); ys.extend([e.dxf.start.y, e.dxf.end.y])
        elif t == "LWPOLYLINE":
            for p in e.get_points("xy"): xs.append(p[0]); ys.append(p[1])
        elif t == "POLYLINE":
            for v in e.vertices: xs.append(v.dxf.location.x); ys.append(v.dxf.location.y)
    for e in msp:
        if e.dxftype() == "INSERT":
            for sub in _walk(e):
                if sub.dxf.layer == "A-WALL":
                    consume(sub)
        elif e.dxf.layer == "A-WALL":
            consume(e)
    return xs, ys


def load_shell(path):
    """Open a base-CAD shell. Returns (doc, msp, OX, OY) where (OX,OY) is the A-WALL min in world coords."""
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    xs, ys = _awall_points(msp)
    if not xs:  # fall back to drawing extents
        bb = ezdxf.bbox.extents(msp, fast=True)
        OX, OY = bb.extmin.x, bb.extmin.y
    else:
        OX, OY = min(xs), min(ys)
    ensure_layers(doc)
    return doc, msp, OX, OY


def ensure_layers(doc):
    for n, c in LAYERS:
        if n not in doc.layers:
            doc.layers.add(n, color=c)


def import_library(doc, names=None):
    """Import block definitions from the trimmed BASE LIBRARY.dxf into doc."""
    lib = ezdxf.readfile(BASE_LIBRARY)
    imp = _importer.Importer(lib, doc)
    if names is None:
        names = [b.name for b in lib.blocks if not b.name.startswith("*") and not b.name.startswith("_")]
    imp.import_blocks([n for n in names if n in lib.blocks])
    imp.finalize()
    return names


def import_clinic_rooms(doc):
    """Import the SINK + RO clinic room blocks (from the 2-clinic library) into doc."""
    lib = ezdxf.readfile(CLINIC_2_LIB)
    imp = _importer.Importer(lib, doc)
    imp.import_blocks([SINK_ROOM_BLOCK, RO_ROOM_BLOCK])
    imp.finalize()


def render_png(doc, out, figsize=(24, 16), dpi=90, bg="#1b1b1b"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    fig = plt.figure(figsize=figsize); ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    fig.patch.set_facecolor(bg)
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace(), finalize=True)
    fig.savefig(out, dpi=dpi, facecolor=bg)
    return out


class Placer:
    """Wraps a doc + local frame and tracks every placed fixture for the audit."""
    def __init__(self, doc, msp, OX, OY):
        self.doc, self.msp, self.OX, self.OY = doc, msp, OX, OY
        self.placed = []   # dicts: name,label,x0,y0,x1,y1,retail,audit

    def place(self, name, tx, ty, rot=0, layer="LK-FF&E WALL", label=None, retail=False, audit=True):
        """Insert block `name` so its bbox-min lands at LOCAL (tx,ty); rotation is free. Returns the local bbox."""
        ref = self.msp.add_blockref(name, (self.OX, self.OY), dxfattribs={"rotation": rot, "layer": layer})
        bb = ezdxf.bbox.extents([ref])
        ref.dxf.insert = (ref.dxf.insert.x + (self.OX + tx) - bb.extmin.x,
                          ref.dxf.insert.y + (self.OY + ty) - bb.extmin.y)
        bb = ezdxf.bbox.extents([ref])
        rec = dict(name=name, label=label or name, x0=bb.extmin.x - self.OX, y0=bb.extmin.y - self.OY,
                   x1=bb.extmax.x - self.OX, y1=bb.extmax.y - self.OY, retail=retail, audit=audit)
        self.placed.append(rec)
        return rec

    def wall_run(self, items, x0, y_low, rot=0, gap=0, every=2):
        """Place a brand-sequenced wall run left->right. items=[(block,label),...]; mirror after every `every` fixtures.
        y_low = bottom of the fixture footprint (back against the wall, fixture depth ~250 toward the aisle)."""
        x = x0
        for i, (name, label) in enumerate(items):
            r = self.place(name, x, y_low, rot=rot, layer="LK-FF&E WALL", label=label, retail=True)
            self.txt(label, x + 40, (y_low - 180) if rot == 0 else (y_low + 285), 95)
            x = r["x1"] + gap
            if i < len(items) - 1 and (i + 1) % every == 0:
                m = self.place("MIRROR", x, y_low, rot=rot, layer="LK-MIRROR", label="MIRROR")
                x = m["x1"] + gap
        return x

    def txt(self, s, x, y, h=130, layer="LK-TEXT", rot=0):
        self.msp.add_text(s, dxfattribs={"height": h, "layer": layer, "rotation": rot,
                                         "insert": (self.OX + x, self.OY + y)})

    def rect(self, x0, y0, x1, y1, layer):
        self.msp.add_lwpolyline([(self.OX + x0, self.OY + y0), (self.OX + x1, self.OY + y0),
                                 (self.OX + x1, self.OY + y1), (self.OX + x0, self.OY + y1)],
                                close=True, dxfattribs={"layer": layer})

    def line(self, x0, y0, x1, y1, layer):
        self.msp.add_line((self.OX + x0, self.OY + y0), (self.OX + x1, self.OY + y1), dxfattribs={"layer": layer})

    def arc(self, cx, cy, r, a0, a1, layer="LENS-DOOR-NEW"):
        self.msp.add_arc((self.OX + cx, self.OY + cy), r, a0, a1, dxfattribs={"layer": layer})

    def fire(self, x, y):
        self.msp.add_circle((self.OX + x, self.OY + y), 95, dxfattribs={"layer": "F-FIRE EXTINGUISHER"})
        self.txt("FE", x - 70, y + 130, 95, "F-FIRE EXTINGUISHER")

    def retail_count(self):
        return sum(1 for p in self.placed if p["retail"])
