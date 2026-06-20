# tests/test_app.py
import os
import json
import ezdxf
from fastapi.testclient import TestClient
import engine.app as app_mod


def _fake_gen(system, user):
    return json.dumps({"placements": [
        {"op": "place", "block": "EURO 1040 x 1175", "x": 2000, "y": 1500},
        {"op": "fire", "x": 500, "y": 500},
        {"op": "fire", "x": 2000, "y": 2000},
        {"op": "fire", "x": 3500, "y": 3500},
    ]})


def _shell_doc():
    doc = ezdxf.new(); doc.layers.add("A-WALL")
    msp = doc.modelspace()
    msp.add_lwpolyline([(1000, 1000), (7000, 1000), (7000, 5000), (1000, 5000)],
                       close=True, dxfattribs={"layer": "A-WALL"})
    return doc


def test_design_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(app_mod, "GENERATE_FN", _fake_gen)
    monkeypatch.setattr(app_mod, "WORK_DIR", str(tmp_path))
    p = tmp_path / "shell.dxf"
    _shell_doc().saveas(p)
    client = TestClient(app_mod.app)
    with open(p, "rb") as f:
        r = client.post("/design", files={"shell": ("shell.dxf", f, "application/dxf")},
                        data={"clinic_count": "2", "target_fixtures": "1",
                              "entry_side": "west", "premium_side": "south"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    job = body["job_id"]
    assert client.get(f"/design/{job}/dxf").status_code == 200
    assert client.get(f"/design/{job}/png").status_code == 200


def test_derive_endpoint(tmp_path):
    p = tmp_path / "shell.dxf"
    _shell_doc().saveas(p)
    client = TestClient(app_mod.app)
    with open(p, "rb") as f:
        r = client.post("/derive", files={"shell": ("shell.dxf", f, "application/dxf")})
    assert r.status_code == 200
    assert set(r.json()) >= {"clinic_count", "target_fixtures", "entry_side", "premium_side"}
