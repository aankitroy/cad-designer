from ezdxf.document import Drawing

from app import edits, query, units

TOOL_SCHEMAS = [
    {
        "name": "list_layers",
        "description": "List all layers with entity counts.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "query_entities",
        "description": (
            "Find entities by layer, type, or nearby text. Use this to resolve vague "
            "references like 'the cash counter' into concrete entity handles before editing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "layer": {"type": "string"},
                "type": {
                    "type": "string",
                    "description": "DXF type e.g. LINE, TEXT, LWPOLYLINE",
                },
                "near_text": {"type": "string"},
            },
        },
    },
    {
        "name": "move_entity",
        "description": "Move an entity by a delta in meters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "dx_m": {"type": "number", "description": "delta X in meters"},
                "dy_m": {"type": "number", "description": "delta Y in meters"},
            },
            "required": ["handle", "dx_m", "dy_m"],
        },
    },
    {
        "name": "add_text_label",
        "description": "Add a text label at a point (meters from origin).",
        "input_schema": {
            "type": "object",
            "properties": {
                "x_m": {"type": "number"},
                "y_m": {"type": "number"},
                "text": {"type": "string"},
                "layer": {"type": "string"},
            },
            "required": ["x_m", "y_m", "text"],
        },
    },
    {
        "name": "add_wall",
        "description": "Add a straight wall between two points (meters).",
        "input_schema": {
            "type": "object",
            "properties": {
                "x1_m": {"type": "number"},
                "y1_m": {"type": "number"},
                "x2_m": {"type": "number"},
                "y2_m": {"type": "number"},
                "layer": {"type": "string"},
            },
            "required": ["x1_m", "y1_m", "x2_m", "y2_m"],
        },
    },
    {
        "name": "delete_entity",
        "description": "Delete an entity by handle.",
        "input_schema": {
            "type": "object",
            "properties": {"handle": {"type": "string"}},
            "required": ["handle"],
        },
    },
    {
        "name": "set_layer",
        "description": "Move an entity to a different layer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "layer": {"type": "string"},
            },
            "required": ["handle", "layer"],
        },
    },
]


def dispatch(doc: Drawing, name: str, args: dict) -> dict:
    """Run a tool call against the doc. Returns {result, change, error}.

    ``result`` is set for read tools, ``change`` for write tools. Distance/coordinate
    args (``*_m``) are interpreted in meters and converted to drawing units.
    """
    try:
        def m(v):
            return units.meters_to_drawing_units(doc, float(v))

        if name == "list_layers":
            return {"result": query.list_layers(doc), "change": None, "error": None}
        if name == "query_entities":
            return {
                "result": query.query_entities(
                    doc,
                    layer=args.get("layer"),
                    type=args.get("type"),
                    near_text=args.get("near_text"),
                ),
                "change": None,
                "error": None,
            }
        if name == "move_entity":
            c = edits.move_entity(doc, args["handle"], m(args["dx_m"]), m(args["dy_m"]))
            return {"result": None, "change": c, "error": None}
        if name == "add_text_label":
            c = edits.add_text_label(
                doc, m(args["x_m"]), m(args["y_m"]), args["text"],
                layer=args.get("layer", "TEXT"),
            )
            return {"result": None, "change": c, "error": None}
        if name == "add_wall":
            c = edits.add_wall(
                doc, m(args["x1_m"]), m(args["y1_m"]), m(args["x2_m"]), m(args["y2_m"]),
                layer=args.get("layer", "WALLS"),
            )
            return {"result": None, "change": c, "error": None}
        if name == "delete_entity":
            return {"result": None, "change": edits.delete_entity(doc, args["handle"]), "error": None}
        if name == "set_layer":
            return {
                "result": None,
                "change": edits.set_layer(doc, args["handle"], args["layer"]),
                "error": None,
            }
        return {"result": None, "change": None, "error": f"Unknown tool {name}"}
    except edits.EntityNotFound as e:
        return {"result": None, "change": None, "error": str(e)}
    except (KeyError, ValueError) as e:
        return {"result": None, "change": None, "error": f"Bad args for {name}: {e}"}
