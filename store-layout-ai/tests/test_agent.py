# tests/test_agent.py
import os
import json
import skilllib
from engine.agent import design


def fake_generate_ok(system, user):
    return json.dumps({"placements": [
        {"op": "place", "block": "EURO 1040 x 1175", "x": 2000, "y": 1500, "rot": 0},
        {"op": "fire", "x": 500, "y": 500},
        {"op": "fire", "x": 2000, "y": 2000},
        {"op": "fire", "x": 3500, "y": 3500},
    ]})


def test_design_success(tiny_shell, tmp_path):
    res = design(tiny_shell, {"clinic_count": 2, "target_fixtures": 1,
                              "entry_side": "west", "premium_side": "south"},
                 out_dir=str(tmp_path), generate_fn=fake_generate_ok)
    assert res["ok"] is True
    assert os.path.isfile(res["dxf"])
    assert os.path.isfile(res["png"])
    assert res["audit"]["passed"] is True
    assert res["attempts"] == 1


def test_design_self_repairs(tiny_shell, tmp_path):
    calls = {"n": 0}

    def flaky(system, user):
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps({"placements": [
                {"op": "place", "block": "EURO 1040 x 1175", "x": 2000, "y": 0}]})  # on column → FAIL
        return fake_generate_ok(system, user)

    res = design(tiny_shell, {"clinic_count": 2, "target_fixtures": 1,
                              "entry_side": "west", "premium_side": "south"},
                 out_dir=str(tmp_path), generate_fn=flaky, max_attempts=3)
    assert res["attempts"] == 2 and res["ok"] is True
