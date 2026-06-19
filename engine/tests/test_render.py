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


def test_pattern_hatch_rendered_as_lines_and_doc_left_clean():
    """Pattern (non-solid) hatches like ANSI31 wall hatching are exploded into lines
    so they show, and the temporary lines are removed from the doc afterwards."""
    doc = ezdxf.new("R2010")
    block = doc.blocks.new("WALL")
    hatch = block.add_hatch()
    hatch.set_pattern_fill("ANSI31", scale=2.0)
    hatch.paths.add_polyline_path(
        [(0, 0), (100, 0), (100, 6), (0, 6)], is_closed=True
    )
    doc.modelspace().add_blockref("WALL", (0, 0))

    before = len(list(doc.modelspace()))
    svg = render_svg(doc)
    after = len(list(doc.modelspace()))

    # explosion produced many hatch line paths...
    assert len(re.findall(r"<path[ >]", svg)) > 5
    # ...and the temporary lines were cleaned up (doc unchanged for download/edit)
    assert after == before


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
