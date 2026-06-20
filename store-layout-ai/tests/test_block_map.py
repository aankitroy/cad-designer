# tests/test_block_map.py
from data.block_map import classify, library_block_names, coverage


def test_library_names_loaded():
    names = library_block_names()
    assert "EURO 1040 x 1175" in names
    assert "JJ SH 1200" in names
    assert len(names) > 40


def test_classify_library_block():
    kind, target = classify("EURO 1040 x 1175")
    assert kind == "library" and target == "EURO 1040 x 1175"


def test_classify_shell_block_is_skip():
    kind, _ = classify("existignn csk")
    assert kind == "skip"


def test_classify_retired_tv_is_substitute():
    kind, target = classify("55INCH")
    assert kind == "substitute" and target["layer"] == "LK-TV SCREEN"


def test_classify_clinic_room_is_library():
    # SINK/RO room blocks resolve via the clinic library
    kind, _ = classify("A$C15b5f610")
    assert kind in ("library", "clinic_room")


def test_coverage_reports_unmapped():
    rep = coverage(["EURO 1040 x 1175", "existignn csk", "TOTALLY UNKNOWN BLOCK"])
    assert "TOTALLY UNKNOWN BLOCK" in rep["unmapped"]
    assert "EURO 1040 x 1175" in rep["library"]
