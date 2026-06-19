import io

import ezdxf
import pytest

from app.components import import_as_block


def _base_doc(insunits=6):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = insunits
    return doc


def test_import_creates_block(component_bytes):
    doc = _base_doc()
    name = import_as_block(doc, component_bytes, "chair.dxf")
    assert name == "chair"
    assert name in doc.blocks
    assert len(list(doc.blocks.get(name))) >= 2
    # modelspace unchanged until something is placed
    assert len(list(doc.modelspace())) == 0


def test_import_handles_binary_chunk_dxf(binary_component_bytes):
    # Real CAD blocks carry group-310 binary data with CRLF endings; the strict
    # text reader fails with "Invalid binary data". import_as_block must use the
    # same recover-mode loader as upload so these files import successfully.
    doc = _base_doc()
    name = import_as_block(doc, binary_component_bytes, "FURNITURE BLOCKS.dxf")
    assert name in doc.blocks
    assert len(list(doc.blocks.get(name))) >= 1


def test_import_bakes_unit_scale(component_bytes):
    # component is mm (500 units = 0.5 m); base is meters -> block should be ~0.5 wide
    doc = _base_doc(insunits=6)
    name = import_as_block(doc, component_bytes, "chair.dxf")
    from ezdxf.bbox import extents

    bb = extents(doc.blocks.get(name))
    assert bb.size.x == pytest.approx(0.5, abs=1e-6)


def test_import_dedupes_name(component_bytes):
    doc = _base_doc()
    n1 = import_as_block(doc, component_bytes, "chair.dxf")
    n2 = import_as_block(doc, component_bytes, "chair.dxf")
    assert n1 == "chair" and n2 == "chair_2"


def test_import_rejects_garbage():
    doc = _base_doc()
    with pytest.raises(ValueError):
        import_as_block(doc, b"not a dxf", "x.dxf")


def test_import_rejects_empty_geometry():
    empty = ezdxf.new("R2010")
    buf = io.StringIO()
    empty.write(buf)
    doc = _base_doc()
    with pytest.raises(ValueError):
        import_as_block(doc, buf.getvalue().encode(), "empty.dxf")
