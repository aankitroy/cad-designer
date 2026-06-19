import ezdxf

from app.space import drawing_bounds


def test_bounds_of_sample(sample_doc):
    b = drawing_bounds(sample_doc["doc"])
    assert b is not None
    min_x, min_y, max_x, max_y = b
    assert (round(min_x), round(min_y)) == (0, 0)
    assert (round(max_x), round(max_y)) == (10, 8)


def test_bounds_empty_modelspace():
    doc = ezdxf.new("R2010")
    assert drawing_bounds(doc) is None


from app.space import compute_frame


def test_frame_bounds_and_anchors_meters(sample_doc):
    f = compute_frame(sample_doc["doc"])
    b = f["bounds_m"]
    assert (round(b["width"]), round(b["depth"])) == (10, 8)
    a = f["anchors_m"]
    assert [round(v) for v in a["center"]] == [5, 4]
    # default: front = min_y edge, back = max_y edge
    assert [round(v) for v in a["front_center"]] == [5, 0]
    assert [round(v) for v in a["back_center"]] == [5, 8]
    assert [round(v) for v in a["back_left"]] == [0, 8]


def test_frame_unit_conversion_mm():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm
    doc.modelspace().add_lwpolyline(
        [(0, 0), (10000, 0), (10000, 8000), (0, 8000), (0, 0)]
    )
    f = compute_frame(doc)
    b = f["bounds_m"]
    assert round(b["width"]) == 10 and round(b["depth"]) == 8  # 10000 mm -> 10 m


def test_frame_default_assumed(sample_doc):
    f = compute_frame(sample_doc["doc"])
    o = f["orientation"]
    assert o["source"] == "assumed"
    assert o["front"] == "min_y" and o["back"] == "max_y" and o["axis"] == "y"


def test_frame_detects_entrance_layer():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (10, 0), (10, 8), (0, 8), (0, 0)])
    doc.layers.add("ENTRANCE")
    # a marker entity near the max_y edge, on the ENTRANCE layer
    msp.add_line((4, 8), (6, 8), dxfattribs={"layer": "ENTRANCE"})
    f = compute_frame(doc)
    o = f["orientation"]
    assert o["source"] == "detected"
    assert o["front"] == "max_y"  # entrance marker sits at the max_y edge
    # back is the opposite edge; back_center should be at min_y
    assert [round(v) for v in f["anchors_m"]["back_center"]] == [5, 0]


def test_frame_user_override_flips_front():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 8), (0, 8), (0, 0)])
    f = compute_frame(doc, orientation_override="north")  # entrance at max_y
    o = f["orientation"]
    assert o["source"] == "user"
    assert o["front"] == "max_y" and o["back"] == "min_y"
    assert [round(v) for v in f["anchors_m"]["back_center"]] == [5, 0]


def test_frame_empty_geometry():
    f = compute_frame(ezdxf.new("R2010"))
    assert f["bounds_m"] is None
    assert "note" in f


from app.space import frame_to_text


def test_frame_to_text_includes_bounds_and_anchors(sample_doc):
    txt = frame_to_text(compute_frame(sample_doc["doc"]))
    assert "10.0" in txt and "8.0" in txt          # width / depth
    assert "back_center" in txt
    assert "assumed" in txt                          # orientation source surfaced


def test_frame_to_text_empty():
    txt = frame_to_text(compute_frame(ezdxf.new("R2010")))
    assert "no renderable geometry" in txt
