# tests/test_executor.py
import os
import ezdxf
import skilllib
from engine.executor import run_script, ExecResult
from data.rules import BANNED_BLOCKS


def test_runs_simple_script_to_dxf(tiny_shell, tmp_path):
    script = ("```python\n"
              "placer.place('EURO 1040 x 1175', x=2000, y=1500, rot=0)\n"
              "```")
    out = tmp_path / "out.dxf"
    res = run_script(script, tiny_shell, str(out))
    assert isinstance(res, ExecResult)
    assert res.error is None
    assert os.path.isfile(out)
    assert len(res.placer.placed) == 1
    ezdxf.readfile(out)  # round-trips


def test_banned_block_is_rejected_before_exec(tiny_shell, tmp_path):
    script = "```python\nplacer.place('55INCH', x=0, y=0)\n```"
    res = run_script(script, tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is not None
    assert "banned" in res.error.lower()


def test_syntax_error_is_captured(tiny_shell, tmp_path):
    res = run_script("```python\nplacer.place(\n```", tiny_shell, str(tmp_path / "o.dxf"))
    assert res.error is not None
