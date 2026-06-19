from ezdxf.bbox import extents
from ezdxf.document import Drawing


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
