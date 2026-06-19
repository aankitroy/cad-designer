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
