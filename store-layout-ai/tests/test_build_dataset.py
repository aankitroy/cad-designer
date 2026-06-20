# tests/test_build_dataset.py
import os
import skilllib
from data.build_dataset import build_record, roundtrip_ok, discover_pairs


def test_discover_finds_12_pairs():
    pairs = discover_pairs()
    assert len(pairs) >= 12
    shell, fp = pairs[0]
    assert os.path.isfile(shell) and os.path.isfile(fp)


def test_build_record_shape():
    shell, fp = discover_pairs()[0]
    rec = build_record(shell, fp)
    roles = [m["role"] for m in rec["messages"]]
    assert roles == ["system", "user", "assistant"]
    assert "SHELL:" in rec["messages"][1]["content"]
    assert "PARAMS:" in rec["messages"][1]["content"]
    assert "placer.place(" in rec["messages"][2]["content"]


def test_roundtrip_executes(tmp_path):
    shell, fp = discover_pairs()[0]
    rec = build_record(shell, fp)
    ok, detail = roundtrip_ok(rec, shell, str(tmp_path / "rt.dxf"))
    assert ok, detail
