from app.render import render_svg


def test_render_returns_svg_string(sample_doc):
    svg = render_svg(sample_doc["doc"])
    assert isinstance(svg, str)
    assert svg.lstrip().startswith("<")
    assert "svg" in svg[:200].lower()
