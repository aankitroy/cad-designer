# tests/test_agent.py
import os
import skilllib
from engine.agent import design


def fake_generate_ok(system, user):
    return ("```python\n"
            "placer.place('EURO 1040 x 1175', x=2000, y=1500, rot=0)\n"
            "placer.fire(500, 500)\nplacer.fire(2000, 2000)\nplacer.fire(3500, 3500)\n"
            "```")


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
            return "```python\nplacer.place('EURO 1040 x 1175', x=2000, y=0)\n```"  # on column → FAIL
        return fake_generate_ok(system, user)

    res = design(tiny_shell, {"clinic_count": 2, "target_fixtures": 1,
                              "entry_side": "west", "premium_side": "south"},
                 out_dir=str(tmp_path), generate_fn=flaky, max_attempts=3)
    assert res["attempts"] == 2 and res["ok"] is True
