from ezdxf.document import Drawing


def _layer_of(e) -> str | None:
    """Layer name, or None for non-graphical entities that lack the attribute."""
    if e.dxf.hasattr("layer"):
        return e.dxf.layer
    return None


def list_layers(doc: Drawing) -> list[dict]:
    msp = doc.modelspace()
    counts: dict[str, int] = {}
    for e in msp:
        layer = _layer_of(e)
        if layer is not None:
            counts[layer] = counts.get(layer, 0) + 1
    return [
        {"name": layer.dxf.name, "entity_count": counts.get(layer.dxf.name, 0)}
        for layer in doc.layers
    ]


def _entity_text(e) -> str | None:
    if e.dxftype() == "TEXT":
        return e.dxf.text
    if e.dxftype() == "MTEXT":
        return e.text
    return None


def _entity_point(e):
    try:
        if e.dxftype() == "LINE":
            return (e.dxf.start.x, e.dxf.start.y)
        if e.dxftype() == "CIRCLE":
            return (e.dxf.center.x, e.dxf.center.y)
        if e.dxftype() in ("TEXT", "INSERT"):
            return (e.dxf.insert.x, e.dxf.insert.y)
        if e.dxftype() == "LWPOLYLINE":
            pts = list(e.get_points())
            return (pts[0][0], pts[0][1]) if pts else None
    except Exception:
        return None
    return None


def query_entities(
    doc: Drawing,
    layer: str | None = None,
    type: str | None = None,
    near_text: str | None = None,
    near_point: tuple[float, float] | None = None,
    radius: float | None = None,
) -> list[dict]:
    msp = doc.modelspace()
    out: list[dict] = []
    for e in msp:
        e_layer = _layer_of(e)
        if e_layer is None:
            continue  # skip non-graphical entities
        if layer and e_layer != layer:
            continue
        if type and e.dxftype() != type.upper():
            continue
        text = _entity_text(e)
        if near_text and (text is None or near_text.lower() not in text.lower()):
            continue
        pt = _entity_point(e)
        if near_point and radius is not None and pt is not None:
            dx, dy = pt[0] - near_point[0], pt[1] - near_point[1]
            if (dx * dx + dy * dy) ** 0.5 > radius:
                continue
        out.append(
            {
                "handle": e.dxf.handle,
                "type": e.dxftype(),
                "layer": e_layer,
                "text": text,
                "block": e.dxf.name if e.dxftype() == "INSERT" else None,
                "point": pt,
            }
        )
    return out
