import io
import re

import ezdxf
from ezdxf.addons import importer
from ezdxf.document import Drawing
from ezdxf.math import Matrix44

from app import units


def _unique_block_name(doc: Drawing, filename: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", filename.rsplit(".", 1)[0]) or "component"
    name = base
    i = 2
    while name in doc.blocks:
        name = f"{base}_{i}"
        i += 1
    return name


def import_as_block(doc: Drawing, dxf_bytes: bytes, filename: str) -> str:
    """Import an attached DXF's modelspace into a new block in ``doc``, scaled so the
    block is expressed in ``doc``'s drawing units. Returns the new block name."""
    try:
        src = ezdxf.read(io.StringIO(dxf_bytes.decode("utf-8", errors="replace")))
    except Exception as exc:  # ezdxf.DXFStructureError and friends
        raise ValueError(f"Not a valid DXF file: {exc}") from exc

    if len(list(src.modelspace())) == 0:
        raise ValueError("Attached DXF has no drawable geometry")

    name = _unique_block_name(doc, filename)
    block = doc.blocks.new(name=name)
    imp = importer.Importer(src, doc)
    imp.import_modelspace(target_layout=block)
    imp.finalize()

    scale = units.meters_per_unit(src) / units.meters_per_unit(doc)
    if abs(scale - 1.0) > 1e-9:
        m = Matrix44.scale(scale, scale, scale)
        for entity in block:
            try:
                entity.transform(m)
            except Exception:  # noqa: BLE001 - skip entities that can't transform
                pass
    return name
