# tests/test_reverse_engineer.py
import os
import skilllib
from data.reverse_engineer import fp_to_script


def test_script_is_string_with_place_calls():
    fp = os.path.join(skilllib.BASE_FILES, "BASE 2 FP.dxf")
    script = fp_to_script(fp)
    assert isinstance(script, str)
    assert "placer.place(" in script
    assert "EURO 1040 x 1175" in script


def test_script_skips_shell_block():
    fp = os.path.join(skilllib.BASE_FILES, "BASE 2 FP.dxf")
    script = fp_to_script(fp)
    assert "existignn csk" not in script


def test_script_has_zone_comments():
    fp = os.path.join(skilllib.BASE_FILES, "BASE 2 FP.dxf")
    script = fp_to_script(fp)
    assert "#" in script


from data.reverse_engineer import fp_to_config


def test_config_has_place_ops():
    fp = os.path.join(skilllib.BASE_FILES, "BASE 2 FP.dxf")
    cfg = fp_to_config(fp)
    assert isinstance(cfg, dict)
    blocks = [p["block"] for p in cfg["placements"] if p["op"] == "place"]
    assert "EURO 1040 x 1175" in blocks


def test_config_skips_shell_block():
    fp = os.path.join(skilllib.BASE_FILES, "BASE 2 FP.dxf")
    cfg = fp_to_config(fp)
    assert "existignn csk" not in [p.get("block") for p in cfg["placements"]]


def test_config_ops_all_known():
    fp = os.path.join(skilllib.BASE_FILES, "BASE 2 FP.dxf")
    cfg = fp_to_config(fp)
    assert all(p["op"] in ("place", "rect", "fire") for p in cfg["placements"])
    assert any(p.get("zone") for p in cfg["placements"] if p["op"] == "place")
