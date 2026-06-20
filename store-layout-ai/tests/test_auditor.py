# tests/test_auditor.py
import skilllib
from engine.auditor import (structured_audit, check_walk_around,
                            check_door_access, check_washroom_access)


def _placer_with_one_fixture(tiny_shell):
    doc, msp, OX, OY = skilllib.load_shell(tiny_shell)
    skilllib.import_library(doc)
    placer = skilllib.Placer(doc, msp, OX, OY)
    placer.place("EURO 1040 x 1175", 2000, 1500, retail=True)
    return placer


def _p(label, x0, y0, x1, y1):
    return {"name": label, "label": label, "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "retail": False, "audit": True}


def test_structured_audit_returns_all_checks(tiny_shell):
    placer = _placer_with_one_fixture(tiny_shell)
    struct = skilllib.extract_structure(tiny_shell)
    result = structured_audit(placer, struct, target_count=1)
    assert "checks" in result and "passed" in result
    assert all(set(c) >= {"check", "status", "detail"} for c in result["checks"])
    names = {c["check"] for c in result["checks"]}
    assert {"column_beam_overlap", "fixture_overlap", "walk_around",
            "door_access", "washroom_access"} <= names


def test_overlap_detected_as_fail(tiny_shell):
    doc, msp, OX, OY = skilllib.load_shell(tiny_shell)
    skilllib.import_library(doc)
    placer = skilllib.Placer(doc, msp, OX, OY)
    # place a fixture directly on the column at local (2000,0)..(2300,300)
    placer.place("EURO 1040 x 1175", 2000, 0)
    struct = skilllib.extract_structure(tiny_shell)
    result = structured_audit(placer, struct)
    overlap = next(c for c in result["checks"] if c["check"] == "column_beam_overlap")
    assert overlap["status"] == "FAIL"
    assert result["passed"] is False


# --- circulation / access checks (synthetic inputs, deterministic) ---

def test_walk_around_flags_pinch():
    a = _p("EURO A", 0, 0, 1040, 1175)
    b = _p("EURO B", 0, 1675, 1040, 2850)   # 500 mm gap above A → trap range
    r = check_walk_around([a, b])
    assert r["status"] == "WARN" and "500mm" in r["detail"]


def test_walk_around_ok_when_wide():
    a = _p("EURO A", 0, 0, 1040, 1175)
    b = _p("EURO B", 0, 2375, 1040, 3550)   # 1200 mm gap → walkable
    assert check_walk_around([a, b])["status"] == "PASS"


def test_door_access_blocked_is_fail():
    structure = {"doors": [("ARC", 5000, 500, 800)]}   # swing box (4200,-300)-(5800,1300)
    blocker = _p("EURO", 4300, 200, 5340, 1375)
    assert check_door_access([blocker], structure)["status"] == "FAIL"


def test_door_access_clear_is_pass():
    structure = {"doors": [("ARC", 5000, 500, 800)]}
    far = _p("EURO", 100, 2000, 1140, 3175)
    assert check_door_access([far], structure)["status"] == "PASS"


def test_washroom_blocked_is_fail():
    structure = {"labels": [("TOILET", 5200, 300)]}   # zone (4700,-200)-(5700,800)
    blocker = _p("BOH RACK", 4800, 0, 5400, 600)
    assert check_washroom_access([blocker], structure)["status"] == "FAIL"


def test_washroom_na_without_label():
    assert check_washroom_access([], {"labels": []})["status"] == "N/A"
