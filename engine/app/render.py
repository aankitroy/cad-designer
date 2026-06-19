import logging

from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
from ezdxf.addons.drawing.layout import Page
from ezdxf.addons.drawing.svg import SVGBackend
from ezdxf.document import Drawing

log = logging.getLogger(__name__)

# Render on a white background (CAD files default to a dark screen background).
# COLOR_SWAP_BW keeps real layer colors but swaps white<->black so lines drawn in
# white (invisible on white) become black and stay visible.
_CONFIG = Configuration().with_changes(
    background_policy=BackgroundPolicy.WHITE,
    color_policy=ColorPolicy.COLOR_SWAP_BW,
)


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
        Frontend(ctx, backend, config=_CONFIG).draw_layout(msp)
    except Exception as exc:  # noqa: BLE001
        # Slow, robust path: a single malformed entity blew up the bulk render,
        # so draw entities one at a time and skip the ones that raise.
        log.warning("bulk render failed (%s); falling back to per-entity render", exc)
        backend = SVGBackend()
        frontend = Frontend(ctx, backend, config=_CONFIG)
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
