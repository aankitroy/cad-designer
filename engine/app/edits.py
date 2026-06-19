from ezdxf.document import Drawing


class EntityNotFound(Exception):
    pass


class ComponentNotFound(Exception):
    pass


def _get(doc: Drawing, handle: str):
    e = doc.entitydb.get(handle)
    if e is None or not e.is_alive:
        raise EntityNotFound(f"No entity with handle {handle}")
    return e


def ensure_layer(doc: Drawing, name: str, color: int = 7) -> bool:
    """Create the layer if it doesn't exist. Returns True if newly created."""
    if name in doc.layers:
        return False
    doc.layers.add(name, color=color)
    return True


def create_layer(doc: Drawing, name: str, color: int = 7) -> dict:
    created = ensure_layer(doc, name, color)
    return {
        "op": "create_layer",
        "handle": "",
        "before": None,
        "after": name,
        "summary": (f"Created layer '{name}'" if created else f"Layer '{name}' already exists"),
    }


def _summarize_point(e):
    try:
        if e.dxftype() == "LINE":
            return [e.dxf.start.x, e.dxf.start.y]
        if e.dxftype() in ("TEXT", "INSERT"):
            return [e.dxf.insert.x, e.dxf.insert.y]
        if e.dxftype() == "CIRCLE":
            return [e.dxf.center.x, e.dxf.center.y]
    except Exception:
        return None
    return None


def move_entity(doc: Drawing, handle: str, dx: float, dy: float) -> dict:
    e = _get(doc, handle)
    before = _summarize_point(e)
    e.translate(dx, dy, 0)
    return {
        "op": "move_entity",
        "handle": handle,
        "before": before,
        "after": _summarize_point(e),
        "summary": f"Moved {e.dxftype()} by ({dx}, {dy})",
    }


def delete_entity(doc: Drawing, handle: str) -> dict:
    e = _get(doc, handle)
    etype = e.dxftype()
    doc.modelspace().delete_entity(e)
    return {
        "op": "delete_entity",
        "handle": handle,
        "before": etype,
        "after": None,
        "summary": f"Deleted {etype}",
    }


def add_text_label(
    doc: Drawing, x: float, y: float, text: str, layer: str = "TEXT", height: float = 0.3
) -> dict:
    msp = doc.modelspace()
    ensure_layer(doc, layer)
    t = msp.add_text(text, dxfattribs={"layer": layer, "height": height})
    t.set_placement((x, y))
    return {
        "op": "add_text_label",
        "handle": t.dxf.handle,
        "before": None,
        "after": text,
        "summary": f"Added label '{text}' at ({x}, {y})",
    }


def add_wall(
    doc: Drawing, x1: float, y1: float, x2: float, y2: float, layer: str = "WALLS"
) -> dict:
    msp = doc.modelspace()
    ensure_layer(doc, layer)
    p = msp.add_lwpolyline([(x1, y1), (x2, y2)], dxfattribs={"layer": layer})
    return {
        "op": "add_wall",
        "handle": p.dxf.handle,
        "before": None,
        "after": [(x1, y1), (x2, y2)],
        "summary": f"Added wall ({x1},{y1})->({x2},{y2})",
    }


def place_component(
    doc: Drawing, name: str, x: float, y: float, rotation_deg: float = 0.0, scale: float = 1.0
) -> dict:
    if name not in doc.blocks:
        raise ComponentNotFound(f"No component named {name!r}")
    ins = doc.modelspace().add_blockref(
        name,
        (x, y),
        dxfattribs={"xscale": scale, "yscale": scale, "rotation": rotation_deg},
    )
    return {
        "op": "place_component",
        "handle": ins.dxf.handle,
        "before": None,
        "after": name,
        "summary": f"Placed '{name}' at ({x}, {y})",
    }


def rotate_entity(doc: Drawing, handle: str, angle_deg: float) -> dict:
    import math as _math

    from ezdxf.math import Matrix44

    e = _get(doc, handle)
    if e.dxftype() == "INSERT":
        before = e.dxf.rotation
        e.dxf.rotation = (e.dxf.rotation + angle_deg) % 360
        after = e.dxf.rotation
    else:
        pt = _summarize_point(e) or [0.0, 0.0]
        m = (
            Matrix44.translate(-pt[0], -pt[1], 0)
            @ Matrix44.z_rotate(_math.radians(angle_deg))
            @ Matrix44.translate(pt[0], pt[1], 0)
        )
        e.transform(m)
        before, after = 0.0, angle_deg
    return {
        "op": "rotate_entity",
        "handle": handle,
        "before": before,
        "after": after,
        "summary": f"Rotated {e.dxftype()} by {angle_deg}°",
    }


def set_layer(doc: Drawing, handle: str, layer: str) -> dict:
    e = _get(doc, handle)
    before = e.dxf.layer
    ensure_layer(doc, layer)
    e.dxf.layer = layer
    return {
        "op": "set_layer",
        "handle": handle,
        "before": before,
        "after": layer,
        "summary": f"Moved {e.dxftype()} to layer {layer}",
    }
