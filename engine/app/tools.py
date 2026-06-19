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
        "name": "place_component",
        "description": (
            "Place a previously-attached component (a block, by name) into the drawing "
            "at a point in meters. The component is CENTERED on (x_m, y_m), so use a "
            "DRAWING FRAME anchor (e.g. back_center) directly. rotation_deg rotates the "
            "placement; scale multiplies its size (1.0 = real size). layer sets which "
            "layer it lands on (defaults to 'Furniture' so placements stack as their own "
            "toggleable layer over the base)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "component/block name"},
                "x_m": {"type": "number"},
                "y_m": {"type": "number"},
                "rotation_deg": {"type": "number"},
                "scale": {"type": "number"},
                "layer": {"type": "string", "description": "target layer, e.g. 'Furniture'"},
            },
            "required": ["name", "x_m", "y_m"],
        },
    },
    {
        "name": "rotate_entity",
        "description": "Rotate an entity (e.g. a placed component) by angle_deg degrees.",
        "input_schema": {
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "angle_deg": {"type": "number"},
            },
            "required": ["handle", "angle_deg"],
        },
    },
    {
        "name": "create_layer",
        "description": (
            "Create a new layer (or confirm one exists) so additions can be organized "
            "onto it. e.g. create_layer('Furniture') then add_wall/add_text_label with "
            "layer='Furniture'. Adding to a non-existent layer also auto-creates it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "color": {"type": "integer", "description": "ACI color 1-255, optional"},
            },
            "required": ["name"],
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
    {
        "name": "set_entrance",
        "description": (
            "Record which wall/edge the store ENTRANCE is on, when the user tells "
            "you the orientation (e.g. 'the entrance is on the left'). Use the DRAWING "
            "FRAME's edge names. side is one of: north/top, south/bottom, east/right, "
            "west/left. This re-orients front/back/left/right for the rest of the session."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"side": {"type": "string"}},
            "required": ["side"],
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
        if name == "create_layer":
            c = edits.create_layer(doc, args["name"], int(args.get("color", 7)))
            return {"result": None, "change": c, "error": None}
        if name == "place_component":
            c = edits.place_component(
                doc, args["name"], m(args["x_m"]), m(args["y_m"]),
                rotation_deg=float(args.get("rotation_deg", 0.0)),
                scale=float(args.get("scale", 1.0)),
                layer=args.get("layer") or "Furniture",
            )
            return {"result": None, "change": c, "error": None}
        if name == "rotate_entity":
            c = edits.rotate_entity(doc, args["handle"], float(args["angle_deg"]))
            return {"result": None, "change": c, "error": None}
        if name == "set_entrance":
            return {"result": {"set_entrance": str(args["side"])},
                    "change": None, "error": None}
        return {"result": None, "change": None, "error": f"Unknown tool {name}"}
    except (edits.EntityNotFound, edits.ComponentNotFound) as e:
        return {"result": None, "change": None, "error": str(e)}
    except (KeyError, ValueError) as e:
        return {"result": None, "change": None, "error": f"Bad args for {name}: {e}"}
