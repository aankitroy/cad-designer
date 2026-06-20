# tests/test_derive_params.py
import os
import skilllib
from data.derive_params import derive_params


def test_params_shape():
    fp = os.path.join(skilllib.BASE_FILES, "BASE 2 FP.dxf")
    p = derive_params(fp)
    assert set(p) == {"clinic_count", "target_fixtures", "entry_side", "premium_side"}
    assert p["clinic_count"] in (2, 3, 4)
    assert isinstance(p["target_fixtures"], int) and p["target_fixtures"] > 0
    assert p["entry_side"] in ("west", "east", "north", "south")
    assert p["premium_side"] in ("north", "south", "east", "west")
