from ezdxf.document import Drawing

from app import units
from app.space import drawing_bounds

_VIEWBOX_MAX = 1_000_000.0


def svg_view(doc: Drawing) -> dict | None:
    """The linear map between the rendered SVG's viewBox and world (drawing-unit)
    coordinates. Mirrors ezdxf SVGBackend + auto Page(0,0): longer world side ->
    1,000,000, aspect preserved, origin (0,0), Y-flipped. Returns None if empty."""
    bounds = drawing_bounds(doc)
    if bounds is None:
        return None
    min_x, min_y, max_x, max_y = bounds
    world_w = max_x - min_x
    world_h = max_y - min_y
    longest = max(world_w, world_h)
    if longest <= 0:
        return None
    s = _VIEWBOX_MAX / longest
    return {
        "world": [min_x, min_y, max_x, max_y],
        "viewBox": [0.0, 0.0, world_w * s, world_h * s],
        "meters_per_unit": units.meters_per_unit(doc),
    }
