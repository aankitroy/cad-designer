from ezdxf.document import Drawing


def list_layers(doc: Drawing) -> list[dict]:
    msp = doc.modelspace()
    counts: dict[str, int] = {}
    for e in msp:
        counts[e.dxf.layer] = counts.get(e.dxf.layer, 0) + 1
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
        if layer and e.dxf.layer != layer:
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
                "layer": e.dxf.layer,
                "text": text,
                "point": pt,
            }
        )
    return out
