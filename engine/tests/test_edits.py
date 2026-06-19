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


def test_move_missing_handle_raises(sample_doc):
    with pytest.raises(edits.EntityNotFound):
        edits.move_entity(sample_doc["doc"], "DEADBEEF", dx=1, dy=1)
