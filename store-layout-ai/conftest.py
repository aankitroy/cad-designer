import os, sys
import pytest
import ezdxf

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


@pytest.fixture
def tiny_shell(tmp_path):
    """A minimal valid shell: a closed A-WALL rectangle 6000x4000 + one column.
    Returns the file path. Local origin (A-WALL min) will be (1000,1000) in world."""
    doc = ezdxf.new()
    doc.layers.add("A-WALL")
    doc.layers.add("column")
    msp = doc.modelspace()
    msp.add_lwpolyline([(1000, 1000), (7000, 1000), (7000, 5000), (1000, 5000)],
                       close=True, dxfattribs={"layer": "A-WALL"})
    msp.add_lwpolyline([(3000, 1000), (3300, 1000), (3300, 1300), (3000, 1300)],
                       close=True, dxfattribs={"layer": "column"})
    p = tmp_path / "tiny_shell.dxf"
    doc.saveas(p)
    return str(p)
