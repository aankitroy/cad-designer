import logging

from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import (
    BackgroundPolicy,
    ColorPolicy,
    Configuration,
    HatchPolicy,
)
from ezdxf.addons.drawing.layout import Page
from ezdxf.addons.drawing.svg import SVGBackend
from ezdxf.document import Drawing
from ezdxf.math import Matrix44
from ezdxf.render import hatching

log = logging.getLogger(__name__)

# Render as a clean architectural drawing: white background with dark monochrome
# lines (MONOCHROME_LIGHT_BG), the way a floor plan reads on paper. NORMAL hatch
# policy keeps solid hatches (e.g. columns) filled. ezdxf's frontend does not expand
# pattern hatches (ANSI31 wall hatching) into lines, so we generate those ourselves
# in _inject_pattern_hatch_lines below.
_CONFIG = Configuration().with_changes(
    background_policy=BackgroundPolicy.WHITE,
    color_policy=ColorPolicy.MONOCHROME_LIGHT_BG,
    hatch_policy=HatchPolicy.NORMAL,
)

_MAX_INSERT_DEPTH = 4


def _collect_pattern_hatch_segments(layout, doc: Drawing, m: Matrix44, out: list, depth: int = 0) -> None:
    """Walk a layout/block, exploding non-solid (pattern) hatches into world-space
    line segments. Hatches are exploded in their own block-local coordinates — where
    the pattern math is correct — then each segment is transformed to world space by
    the accumulated INSERT matrix ``m``."""
    for e in layout:
        etype = e.dxftype()
        if etype == "HATCH" and not e.dxf.solid_fill:
            try:
                for a, b in hatching.hatch_entity(e):
                    out.append((m.transform(a), m.transform(b)))
            except Exception as exc:  # noqa: BLE001 - hatch may be degenerate/dense
                log.warning("could not explode hatch pattern: %s", exc)
        elif etype == "INSERT" and depth < _MAX_INSERT_DEPTH:
            block = doc.blocks.get(e.dxf.name)
            if block is not None:
                _collect_pattern_hatch_segments(block, doc, e.matrix44() @ m, out, depth + 1)


def _inject_pattern_hatch_lines(doc: Drawing) -> list:
    """Add pattern-hatch lines to modelspace as temporary LINE entities and return
    them so the caller can remove them after rendering (keeps the saved doc clean)."""
    msp = doc.modelspace()
    segments: list = []
    _collect_pattern_hatch_segments(msp, doc, Matrix44(), segments)
    added = []
    for a, b in segments:
        added.append(msp.add_line((a.x, a.y), (b.x, b.y), dxfattribs={"layer": "0"}))
    return added


def render_svg(doc: Drawing) -> str:
    """Render modelspace to a standalone, auto-sized SVG string.

    Pattern hatches (e.g. diagonal wall hatching) are generated as temporary lines
    first. Real-world DXFs exported by other CAD tools often contain individual
    entities that fail to render (e.g. a LEADER referencing a missing dimstyle), so
    if the one-pass render raises we fall back to drawing entities one at a time and
    skip the ones that fail — a single bad entity never blanks the whole drawing.
    """
    msp = doc.modelspace()
    ctx = RenderContext(doc)
    injected = _inject_pattern_hatch_lines(doc)

    try:
        backend = SVGBackend()
        try:
            Frontend(ctx, backend, config=_CONFIG).draw_layout(msp)
        except Exception as exc:  # noqa: BLE001
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
    finally:
        for line in injected:
            msp.delete_entity(line)
