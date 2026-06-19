import re

import ezdxf

from app.render import render_svg
from app.view import svg_view


def test_view_matches_rendered_viewbox(sample_doc):
    doc = sample_doc["doc"]
    v = svg_view(doc)
    assert v is not None
    assert [round(c) for c in v["world"]] == [0, 0, 10, 8]
    assert v["meters_per_unit"] == 1.0
    svg = render_svg(doc)
    vb = re.search(r'viewBox="([^"]+)"', svg[:400]).group(1)
    rendered = [round(float(x)) for x in vb.split()]
    assert [round(x) for x in v["viewBox"]] == rendered


def test_view_aspect_preserved(sample_doc):
    v = svg_view(sample_doc["doc"])
    _, _, vw, vh = v["viewBox"]
    assert abs((vw / vh) - (10 / 8)) < 1e-6
    assert max(vw, vh) == 1_000_000


def test_view_empty_modelspace():
    assert svg_view(ezdxf.new("R2010")) is None
