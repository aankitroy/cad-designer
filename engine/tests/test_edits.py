import pytest

from app import edits


def test_move_entity(sample_doc):
    doc = sample_doc["doc"]
    h = sample_doc["line_handle"]
    change = edits.move_entity(doc, h, dx=1.0, dy=2.0)
    assert change["op"] == "move_entity"
    assert change["handle"] == h
    line = doc.entitydb[h]
    assert line.dxf.start.x == pytest.approx(3.0)  # was (2,2)
    assert line.dxf.start.y == pytest.approx(4.0)


def test_delete_entity(sample_doc):
    doc = sample_doc["doc"]
    h = sample_doc["line_handle"]
    change = edits.delete_entity(doc, h)
    assert change["op"] == "delete_entity"
    e = doc.entitydb.get(h)
    assert e is None or e.is_alive is False


def test_add_text_label(sample_doc):
    doc = sample_doc["doc"]
    change = edits.add_text_label(doc, x=5, y=5, text="FITTING ROOM", layer="TEXT")
    assert change["op"] == "add_text_label"
    new = doc.entitydb[change["handle"]]
    assert new.dxf.text == "FITTING ROOM"
    assert new.dxf.layer == "TEXT"


def test_add_wall(sample_doc):
    doc = sample_doc["doc"]
    change = edits.add_wall(doc, x1=0, y1=0, x2=5, y2=0, layer="WALLS")
    assert change["op"] == "add_wall"
    new = doc.entitydb[change["handle"]]
    assert new.dxftype() == "LWPOLYLINE"
    assert new.dxf.layer == "WALLS"


def test_set_layer(sample_doc):
    doc = sample_doc["doc"]
    h = sample_doc["line_handle"]
    change = edits.set_layer(doc, h, "WALLS")
    assert doc.entitydb[h].dxf.layer == "WALLS"
    assert change["before"] == "FIXTURES"


def test_create_layer(sample_doc):
    doc = sample_doc["doc"]
    change = edits.create_layer(doc, "FURNITURE", color=3)
    assert change["op"] == "create_layer"
    assert "FURNITURE" in doc.layers


def test_add_wall_auto_creates_layer(sample_doc):
    doc = sample_doc["doc"]
    assert "ELECTRICAL" not in doc.layers
    edits.add_wall(doc, 0, 0, 1, 1, layer="ELECTRICAL")
    assert "ELECTRICAL" in doc.layers


def test_set_layer_auto_creates_layer(sample_doc):
    doc = sample_doc["doc"]
    edits.set_layer(doc, sample_doc["line_handle"], "NEWLAYER")
    assert "NEWLAYER" in doc.layers


def test_move_missing_handle_raises(sample_doc):
    with pytest.raises(edits.EntityNotFound):
        edits.move_entity(sample_doc["doc"], "DEADBEEF", dx=1, dy=1)


def _import_component(doc, insunits=6):
    import io

    import ezdxf

    from app.components import import_as_block

    cdoc = ezdxf.new("R2010")
    cdoc.header["$INSUNITS"] = insunits
    cdoc.modelspace().add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    buf = io.StringIO()
    cdoc.write(buf)
    return import_as_block(doc, buf.getvalue().encode(), "c.dxf")


def test_place_component(sample_doc):
    from ezdxf.bbox import extents

    doc = sample_doc["doc"]
    name = _import_component(doc)
    change = edits.place_component(doc, name, x=5, y=5, rotation_deg=90, scale=2.0)
    assert change["op"] == "place_component"
    ins = doc.entitydb[change["handle"]]
    assert ins.dxftype() == "INSERT"
    assert ins.dxf.name == name
    assert ins.dxf.rotation == 90
    assert ins.dxf.xscale == 2.0
    # the block's geometry is centered on the target, regardless of base point
    bb = extents([ins])
    cx = (bb.extmin.x + bb.extmax.x) / 2
    cy = (bb.extmin.y + bb.extmax.y) / 2
    assert abs(cx - 5) < 1e-6 and abs(cy - 5) < 1e-6


def test_place_component_centers_offset_block(sample_doc):
    # a block whose geometry sits far from its own origin must still land on target
    import io

    import ezdxf
    from ezdxf.bbox import extents

    from app.components import import_as_block

    doc = sample_doc["doc"]
    cdoc = ezdxf.new("R2010")
    cdoc.header["$INSUNITS"] = 6
    cdoc.modelspace().add_lwpolyline(
        [(1000, 1000), (1002, 1000), (1002, 1001), (1000, 1001), (1000, 1000)]
    )
    buf = io.StringIO()
    cdoc.write(buf)
    name = import_as_block(doc, buf.getvalue().encode(), "offset.dxf")
    ch = edits.place_component(doc, name, x=5, y=5)
    bb = extents([doc.entitydb[ch["handle"]]])
    cx = (bb.extmin.x + bb.extmax.x) / 2
    cy = (bb.extmin.y + bb.extmax.y) / 2
    assert abs(cx - 5) < 1e-6 and abs(cy - 5) < 1e-6


def test_place_component_sets_layer(sample_doc):
    doc = sample_doc["doc"]
    name = _import_component(doc)
    ch = edits.place_component(doc, name, x=1, y=1, layer="Furniture")
    ins = doc.entitydb[ch["handle"]]
    assert ins.dxf.layer == "Furniture"
    assert "Furniture" in doc.layers


def test_place_component_unknown_block(sample_doc):
    with pytest.raises(edits.ComponentNotFound):
        edits.place_component(sample_doc["doc"], "nope", x=0, y=0)


def test_rotate_insert(sample_doc):
    doc = sample_doc["doc"]
    name = _import_component(doc)
    ch = edits.place_component(doc, name, x=0, y=0)
    rot = edits.rotate_entity(doc, ch["handle"], 45)
    assert rot["op"] == "rotate_entity"
    assert doc.entitydb[ch["handle"]].dxf.rotation == 45


def test_rotate_line_about_its_point(sample_doc):
    change = edits.rotate_entity(sample_doc["doc"], sample_doc["line_handle"], 90)
    assert change["op"] == "rotate_entity"


def test_rotate_missing_handle(sample_doc):
    with pytest.raises(edits.EntityNotFound):
        edits.rotate_entity(sample_doc["doc"], "DEADBEEF", 30)
