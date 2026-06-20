import os
import skilllib


def test_skill_paths_exist():
    assert os.path.isdir(skilllib.SCRIPTS)
    assert os.path.isfile(os.path.join(skilllib.ASSETS, "BASE LIBRARY.dxf"))
    assert os.path.isdir(skilllib.BASE_FILES)


def test_reexports_callable():
    for name in ["load_shell", "import_library", "Placer", "extract_structure", "audit"]:
        assert callable(getattr(skilllib, name))


def test_load_tiny_shell(tiny_shell):
    doc, msp, OX, OY = skilllib.load_shell(tiny_shell)
    assert (round(OX), round(OY)) == (1000, 1000)
