# tests/test_executor.py
import os
import json
import ezdxf
import skilllib
from engine.executor import apply_layout, ExecResult
from data.rules import BANNED_BLOCKS


def test_no_code_execution_in_executor():
    import inspect
    import engine.executor as ex
    src = inspect.getsource(ex)
    assert "exec(" not in src
    assert "compile(" not in src


def _cfg(placements):
    return json.dumps({"placements": placements})


def test_apply_simple_config_to_dxf(tiny_shell, tmp_path):
    cfg = _cfg([{"op": "place", "block": "EURO 1040 x 1175", "x": 2000, "y": 1500, "rot": 0}])
    out = tmp_path / "out.dxf"
    res = apply_layout(cfg, tiny_shell, str(out))
    assert res.error is None
    assert os.path.isfile(out)
    assert len(res.placer.placed) == 1
    ezdxf.readfile(out)  # round-trips


def test_apply_accepts_fenced_json(tiny_shell, tmp_path):
    cfg = "```json\n" + _cfg([{"op": "place", "block": "EURO 1040 x 1175", "x": 2000, "y": 1500}]) + "\n```"
    res = apply_layout(cfg, tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is None and len(res.placer.placed) == 1


def test_apply_recovers_truncated_array(tiny_shell, tmp_path):
    # third object is cut off (no closing brace / fence) — the two complete ones must still apply
    text = ('{"placements": [\n'
            '{"op":"place","block":"EURO 1040 x 1175","x":2000,"y":1500},\n'
            '{"op":"place","block":"EURO 1040 x 1175","x":4000,"y":1500},\n'
            '{"op":"place","block":"EURO 1040 x')
    res = apply_layout(text, tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is None
    assert len(res.placer.placed) == 2
    assert res.warnings  # recovery recorded a warning


def test_apply_skips_invalid_op(tiny_shell, tmp_path):
    cfg = _cfg([{"op": "place", "block": "EURO 1040 x 1175", "x": 2000, "y": 1500},
                {"op": "place", "block": "EURO 1040 x 1175"}])  # missing x/y
    res = apply_layout(cfg, tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is None
    assert len(res.placer.placed) == 1
    assert res.warnings


def test_apply_rejects_banned_block(tiny_shell, tmp_path):
    cfg = _cfg([{"op": "place", "block": "55INCH", "x": 0, "y": 0}])
    res = apply_layout(cfg, tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is not None and "banned" in res.error.lower()


def test_apply_unparseable_returns_error(tiny_shell, tmp_path):
    res = apply_layout("not json at all <<<", tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is not None


def test_apply_zero_valid_placements_errors(tiny_shell, tmp_path):
    cfg = _cfg([{"op": "frobnicate", "x": 1}])
    res = apply_layout(cfg, tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is not None and "no valid placements" in res.error.lower()
