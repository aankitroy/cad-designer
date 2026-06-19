from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.layout import Page
from ezdxf.addons.drawing.svg import SVGBackend
from ezdxf.document import Drawing


def render_svg(doc: Drawing) -> str:
    """Render modelspace to a standalone, auto-sized SVG string."""
    msp = doc.modelspace()
    backend = SVGBackend()
    Frontend(RenderContext(doc), backend).draw_layout(msp)
    page = Page(0, 0)  # width=height=0 -> auto-size from content bounding box
    return backend.get_string(page)
