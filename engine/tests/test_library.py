import ezdxf

from app import library


def _make_lib(tmp_path):
    for name in ["EURO 1040 x 1175.dxf", "CHAIR UNIT.dxf"]:
        doc = ezdxf.new("R2010")
        doc.modelspace().add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        doc.saveas(tmp_path / name)
    return str(tmp_path)


def test_list_components(tmp_path):
    d = _make_lib(tmp_path)
    comps = library.list_components(d)
    names = [c["name"] for c in comps]
    assert names == ["CHAIR UNIT", "EURO 1040 x 1175"]  # sorted by name
    assert all(c["id"] for c in comps)
    assert len({c["id"] for c in comps}) == 2  # unique ids


def test_component_path_roundtrip(tmp_path):
    d = _make_lib(tmp_path)
    comps = library.list_components(d)
    cid = comps[0]["id"]
    p = library.component_path(cid, d)
    assert p is not None and p.endswith(".dxf")


def test_component_path_unknown_and_traversal(tmp_path):
    d = _make_lib(tmp_path)
    assert library.component_path("nope", d) is None
    assert library.component_path("../secret", d) is None


def test_list_missing_dir_is_empty():
    assert library.list_components("/no/such/dir") == []
