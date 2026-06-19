import re

import ezdxf

from app.render import render_svg


def test_render_returns_svg_string(sample_doc):
    svg = render_svg(sample_doc["doc"])
    assert isinstance(svg, str)
    assert svg.lstrip().startswith("<")
    assert "svg" in svg[:200].lower()


def test_render_uses_white_background(sample_doc):
    """CAD files default to a dark screen background; we force white so the drawing
    sits correctly on the app's light canvas."""
    svg = render_svg(sample_doc["doc"])
    fills = re.findall(r'fill="([^"]+)"', svg)
    assert "#ffffff" in [f.lower() for f in fills]
    assert "#212830" not in [f.lower() for f in fills]  # ezdxf's default dark bg


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
