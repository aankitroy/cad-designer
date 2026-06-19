import io

import ezdxf
import pytest


@pytest.fixture
def sample_doc():
    """A small floor plan: one wall, a fixture line, a text label."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6  # meters
    msp = doc.modelspace()

    doc.layers.add("WALLS", color=1)
    doc.layers.add("FIXTURES", color=3)
    doc.layers.add("TEXT", color=7)

    wall = msp.add_lwpolyline(
        [(0, 0), (10, 0), (10, 8), (0, 8), (0, 0)], dxfattribs={"layer": "WALLS"}
    )
    label = msp.add_text("CASH COUNTER", dxfattribs={"layer": "TEXT", "height": 0.3})
    label.set_placement((2, 2))
    line = msp.add_line((2, 2), (4, 2), dxfattribs={"layer": "FIXTURES"})

    return {
        "doc": doc,
        "wall_handle": wall.dxf.handle,
        "label_handle": label.dxf.handle,
        "line_handle": line.dxf.handle,
    }


@pytest.fixture
def sample_bytes(sample_doc):
    """The sample doc serialized to DXF bytes (for upload tests)."""
    buf = io.StringIO()
    sample_doc["doc"].write(buf)
    return buf.getvalue().encode("utf-8")


@pytest.fixture
def component_bytes():
    """A small 'chair' component DXF in millimeters (500x500 box + a back line)."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (500, 0), (500, 500), (0, 500), (0, 0)])
    msp.add_line((100, 500), (400, 500))
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")
