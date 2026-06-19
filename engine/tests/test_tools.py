from app.tools import TOOL_SCHEMAS, dispatch


def test_schemas_have_required_shape():
    names = {t["name"] for t in TOOL_SCHEMAS}
    assert {
        "query_entities",
        "move_entity",
        "add_text_label",
        "add_wall",
        "delete_entity",
        "set_layer",
        "list_layers",
    } <= names
    for t in TOOL_SCHEMAS:
        assert "name" in t and "description" in t and "input_schema" in t


def test_dispatch_query(sample_doc):
    result = dispatch(sample_doc["doc"], "query_entities", {"layer": "WALLS"})
    assert isinstance(result["result"], list)
    assert result["change"] is None


def test_dispatch_move_converts_meters(sample_doc):
    # doc is in meters, so dx_m=2 -> 2 drawing units
    h = sample_doc["line_handle"]
    out = dispatch(
        sample_doc["doc"], "move_entity", {"handle": h, "dx_m": 2.0, "dy_m": 0.0}
    )
    assert out["change"]["op"] == "move_entity"
    line = sample_doc["doc"].entitydb[h]
    assert abs(line.dxf.start.x - 4.0) < 1e-6  # was 2.0


def test_dispatch_create_layer(sample_doc):
    out = dispatch(sample_doc["doc"], "create_layer", {"name": "FURNITURE"})
    assert out["change"]["op"] == "create_layer"
    assert "FURNITURE" in sample_doc["doc"].layers


def test_create_layer_in_schemas():
    assert "create_layer" in {t["name"] for t in TOOL_SCHEMAS}


def test_dispatch_unknown_tool(sample_doc):
    out = dispatch(sample_doc["doc"], "frobnicate", {})
    assert out["error"]


def test_place_and_rotate_in_schemas():
    names = {t["name"] for t in TOOL_SCHEMAS}
    assert {"place_component", "rotate_entity"} <= names


def test_dispatch_place_component_converts_meters(sample_doc):
    import io

    import ezdxf

    from app.components import import_as_block

    doc = sample_doc["doc"]  # meters
    cdoc = ezdxf.new("R2010")
    cdoc.header["$INSUNITS"] = 6
    cdoc.modelspace().add_line((0, 0), (1, 0))
    buf = io.StringIO()
    cdoc.write(buf)
    name = import_as_block(doc, buf.getvalue().encode(), "c.dxf")

    out = dispatch(
        doc, "place_component", {"name": name, "x_m": 3.0, "y_m": 0.0, "rotation_deg": 0}
    )
    assert out["change"]["op"] == "place_component"
    ins = doc.entitydb[out["change"]["handle"]]
    from ezdxf.bbox import extents

    bb = extents([ins])
    cx = (bb.extmin.x + bb.extmax.x) / 2
    assert abs(cx - 3.0) < 1e-6  # block centered at meters base -> 3 units
    # furniture lands on its own layer by default
    assert ins.dxf.layer == "Furniture"
    assert "Furniture" in doc.layers


def test_dispatch_place_component_explicit_layer(sample_doc):
    import io

    import ezdxf

    from app.components import import_as_block

    doc = sample_doc["doc"]
    cdoc = ezdxf.new("R2010")
    cdoc.header["$INSUNITS"] = 6
    cdoc.modelspace().add_line((0, 0), (1, 0))
    buf = io.StringIO()
    cdoc.write(buf)
    name = import_as_block(doc, buf.getvalue().encode(), "c.dxf")

    out = dispatch(
        doc, "place_component",
        {"name": name, "x_m": 1.0, "y_m": 0.0, "layer": "Clinic"},
    )
    ins = doc.entitydb[out["change"]["handle"]]
    assert ins.dxf.layer == "Clinic"


def test_dispatch_rotate(sample_doc):
    out = dispatch(
        sample_doc["doc"], "rotate_entity",
        {"handle": sample_doc["line_handle"], "angle_deg": 30},
    )
    assert out["change"]["op"] == "rotate_entity"


def test_dispatch_place_unknown_component(sample_doc):
    out = dispatch(sample_doc["doc"], "place_component", {"name": "ghost", "x_m": 0, "y_m": 0})
    assert out["error"]


def test_set_entrance_in_schemas():
    names = {t["name"] for t in TOOL_SCHEMAS}
    assert "set_entrance" in names


def test_dispatch_set_entrance(sample_doc):
    out = dispatch(sample_doc["doc"], "set_entrance", {"side": "north"})
    assert out["error"] is None
    assert out["change"] is None
    assert out["result"] == {"set_entrance": "north"}
