from app.query import list_layers, query_entities


def test_list_layers(sample_doc):
    layers = list_layers(sample_doc["doc"])
    names = {l["name"] for l in layers}
    assert {"WALLS", "FIXTURES", "TEXT"} <= names


def test_query_by_layer(sample_doc):
    results = query_entities(sample_doc["doc"], layer="WALLS")
    assert any(e["handle"] == sample_doc["wall_handle"] for e in results)
    assert all(e["layer"] == "WALLS" for e in results)


def test_query_by_near_text(sample_doc):
    results = query_entities(sample_doc["doc"], near_text="cash")
    assert any("CASH" in (e.get("text") or "").upper() for e in results)


def test_query_returns_handles_and_types(sample_doc):
    results = query_entities(sample_doc["doc"])
    sample = results[0]
    assert "handle" in sample and "type" in sample and "layer" in sample


def test_query_reports_block_name_for_inserts():
    import io

    import ezdxf

    from app.components import import_as_block

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    cdoc = ezdxf.new("R2010")
    cdoc.header["$INSUNITS"] = 6
    cdoc.modelspace().add_line((0, 0), (1, 0))
    buf = io.StringIO()
    cdoc.write(buf)
    name = import_as_block(doc, buf.getvalue().encode(), "sofa.dxf")
    doc.modelspace().add_blockref(name, (0, 0))

    results = query_entities(doc, type="INSERT")
    assert any(r.get("block") == name for r in results)
