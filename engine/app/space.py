from ezdxf.bbox import extents
from ezdxf.document import Drawing

from app import units

_ENTRANCE_KEYWORDS = ("door", "entry", "entrance", "glaz", "shutter", "facade")

# Map natural override words to a canonical edge.
_EDGE_ALIASES = {
    "north": "max_y", "top": "max_y", "max_y": "max_y", "back": "max_y",
    "south": "min_y", "bottom": "min_y", "min_y": "min_y", "front": "min_y",
    "east": "max_x", "right": "max_x", "max_x": "max_x",
    "west": "min_x", "left": "min_x", "min_x": "min_x",
}

_OPPOSITE = {"min_y": "max_y", "max_y": "min_y", "min_x": "max_x", "max_x": "min_x"}


def drawing_bounds(doc: Drawing) -> tuple[float, float, float, float] | None:
    """Modelspace extents (min_x, min_y, max_x, max_y) in DRAWING UNITS.
    Returns None when there is no renderable geometry."""
    msp = doc.modelspace()
    try:
        bbox = extents(msp, fast=True)
    except Exception:
        return None
    if not bbox.has_data:
        return None
    return (bbox.extmin.x, bbox.extmin.y, bbox.extmax.x, bbox.extmax.y)


def _entity_xy(e):
    """Best-effort representative (x, y) for an entity, in drawing units."""
    try:
        t = e.dxftype()
        if t == "LINE":
            s, end = e.dxf.start, e.dxf.end
            return ((s.x + end.x) / 2, (s.y + end.y) / 2)
        if t in ("TEXT", "MTEXT", "INSERT"):
            p = e.dxf.insert
            return (p.x, p.y)
        if t == "CIRCLE":
            return (e.dxf.center.x, e.dxf.center.y)
        if t == "LWPOLYLINE":
            pts = list(e.get_points())
            if pts:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                return (sum(xs) / len(xs), sum(ys) / len(ys))
    except Exception:
        return None
    return None


def _entrance_centroid(doc):
    """Centroid (drawing units) of entities whose layer or text matches an
    entrance keyword, or None if nothing matches."""
    msp = doc.modelspace()
    pts = []
    for e in msp:
        layer = (e.dxf.layer or "").lower()
        text = ""
        if e.dxftype() == "TEXT":
            text = (e.dxf.text or "").lower()
        elif e.dxftype() == "MTEXT":
            text = (e.text or "").lower()
        hay = layer + " " + text
        if any(k in hay for k in _ENTRANCE_KEYWORDS):
            xy = _entity_xy(e)
            if xy is not None:
                pts.append(xy)
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _nearest_edge(centroid, bounds):
    """Which edge (min_x/max_x/min_y/max_y) the centroid is closest to."""
    cx, cy = centroid
    min_x, min_y, max_x, max_y = bounds
    dists = {
        "min_x": abs(cx - min_x),
        "max_x": abs(cx - max_x),
        "min_y": abs(cy - min_y),
        "max_y": abs(cy - max_y),
    }
    return min(dists, key=dists.get)


def _orientation(doc, bounds, override):
    if override:
        front = _EDGE_ALIASES.get(override.strip().lower())
        if front is not None:
            return front, "user"
    centroid = _entrance_centroid(doc)
    if centroid is not None:
        return _nearest_edge(centroid, bounds), "detected"
    return "min_y", "assumed"  # Lenskart default: entrance at -y


def compute_frame(doc: Drawing, orientation_override: str | None = None) -> dict:
    """Spatial frame: bounds + orientation + named anchors, in meters."""
    bounds = drawing_bounds(doc)
    if bounds is None:
        return {
            "bounds_m": None,
            "orientation": None,
            "anchors_m": {},
            "note": "drawing has no renderable geometry",
        }

    mpu = units.meters_per_unit(doc)
    min_x, min_y, max_x, max_y = (v * mpu for v in bounds)
    width, depth = max_x - min_x, max_y - min_y

    front, source = _orientation(doc, bounds, orientation_override)
    back = _OPPOSITE[front]
    axis = "y" if front in ("min_y", "max_y") else "x"
    # left/right are the perpendicular edges; "left" = lower coord facing front->back
    if axis == "y":
        left, right = "min_x", "max_x"
    else:
        left, right = "min_y", "max_y"

    cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2

    def edge_point(edge):
        # center point of the named edge
        if edge == "min_x":
            return [min_x, cy]
        if edge == "max_x":
            return [max_x, cy]
        if edge == "min_y":
            return [cx, min_y]
        return [cx, max_y]  # max_y

    def corner(ey, ex):
        x = min_x if ex == "min_x" else max_x
        y = min_y if ey == "min_y" else max_y
        return [x, y]

    anchors = {
        "center": [cx, cy],
        "front_center": edge_point(front),
        "back_center": edge_point(back),
        "left_wall": edge_point(left),
        "right_wall": edge_point(right),
        "front_left": corner(front if axis == "y" else left,
                             left if axis == "y" else front),
        "front_right": corner(front if axis == "y" else right,
                              right if axis == "y" else front),
        "back_left": corner(back if axis == "y" else left,
                            left if axis == "y" else back),
        "back_right": corner(back if axis == "y" else right,
                            right if axis == "y" else back),
    }

    return {
        "bounds_m": {
            "min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y,
            "width": width, "depth": depth,
        },
        "area_sqft": width * depth * 10.7639,
        "orientation": {
            "front": front, "back": back, "left": left, "right": right,
            "axis": axis, "source": source,
        },
        "anchors_m": anchors,
    }


def frame_to_text(frame: dict) -> str:
    if frame.get("bounds_m") is None:
        return f"DRAWING FRAME: {frame.get('note', 'no geometry')}."
    b = frame["bounds_m"]
    o = frame["orientation"]
    lines = [
        f"Drawing is {b['width']:.1f} m wide x {b['depth']:.1f} m deep "
        f"(~{frame['area_sqft']:.0f} sqft). Coordinates are meters; "
        f"x in [{b['min_x']:.1f}, {b['max_x']:.1f}], "
        f"y in [{b['min_y']:.1f}, {b['max_y']:.1f}].",
        f"Orientation ({o['source']}): front={o['front']}, back={o['back']}, "
        f"left={o['left']}, right={o['right']} (front->back axis: {o['axis']}).",
        "Anchor points (meters):",
    ]
    for name, xy in frame["anchors_m"].items():
        lines.append(f"  {name}: ({xy[0]:.1f}, {xy[1]:.1f})")
    return "\n".join(lines)
