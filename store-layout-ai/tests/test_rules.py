# tests/test_rules.py
from data.rules import SYSTEM_PROMPT, BANNED_BLOCKS


def test_system_prompt_has_core_rules():
    s = SYSTEM_PROMPT.lower()
    assert "base library" in s
    assert "column" in s and "beam" in s
    assert "euro" in s
    assert "fire extinguisher" in s or "extinguisher" in s
    assert "placer.place" in SYSTEM_PROMPT          # output-format contract present


def test_banned_blocks_listed():
    for b in ["LOOKER", "NESTING TABLES", "POS", "55INCH"]:
        assert b in BANNED_BLOCKS
