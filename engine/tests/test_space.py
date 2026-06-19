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
