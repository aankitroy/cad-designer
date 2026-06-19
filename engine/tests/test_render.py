import re

import ezdxf

from app.render import render_svg


def test_render_returns_svg_string(sample_doc):
    svg = render_svg(sample_doc["doc"])
    assert isinstance(svg, str)
    assert svg.lstrip().startswith("<")
    assert "svg" in svg[:200].lower()


def test_render_expands_block_inserts():
    """Geometry nested inside a block INSERT (as in real exports like BASE CAD.dxf,
    where all content lives one INSERT deep) must still be drawn."""
    doc = ezdxf.new("R2010")
    block = doc.blocks.new(name="ROOM")
    block.add_lwpolyline([(0, 0), (5, 0), (5, 4), (0, 4), (0, 0)])
    doc.modelspace().add_blockref("ROOM", (0, 0))

    svg = render_svg(doc)
    # The block's polyline should appear as drawn paths, not be skipped.
    assert len(re.findall(r"<path[ >]", svg)) >= 1
