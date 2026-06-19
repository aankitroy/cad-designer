import logging

from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.layout import Page
from ezdxf.addons.drawing.svg import SVGBackend
from ezdxf.document import Drawing

log = logging.getLogger(__name__)


def render_svg(doc: Drawing) -> str:
    """Render modelspace to a standalone, auto-sized SVG string.

    Real-world DXFs exported by other CAD tools often contain individual entities
    that fail to render (e.g. a LEADER referencing a missing dimstyle). We draw
    entities one at a time and skip the ones that raise, so a single bad entity
    never blanks the whole drawing.
    """
    msp = doc.modelspace()
    ctx = RenderContext(doc)

    # Fast path: render the whole layout in one pass.
    backend = SVGBackend()
    try:
        Frontend(ctx, backend).draw_layout(msp)
    except Exception as exc:  # noqa: BLE001
        # Slow, robust path: a single malformed entity blew up the bulk render,
        # so draw entities one at a time and skip the ones that raise.
        log.warning("bulk render failed (%s); falling back to per-entity render", exc)
        backend = SVGBackend()
        frontend = Frontend(ctx, backend)
        skipped = 0
        for entity in msp:
            try:
                frontend.draw_entities([entity])
            except Exception as e:  # noqa: BLE001 - tolerate any malformed entity
                skipped += 1
                log.warning("skipped un-renderable %s: %s", entity.dxftype(), e)
        if skipped:
            log.info("render skipped %d un-renderable entities", skipped)

    page = Page(0, 0)  # width=height=0 -> auto-size from content bounding box
    return backend.get_string(page)
