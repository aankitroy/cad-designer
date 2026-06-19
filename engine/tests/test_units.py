import ezdxf
import pytest

from app.units import current_units, meters_to_drawing_units, set_units


def test_meters_when_doc_in_meters(sample_doc):
    # $INSUNITS == 6 (meters): 2m -> 2.0 drawing units
    assert meters_to_drawing_units(sample_doc["doc"], 2.0) == 2.0


def test_meters_when_doc_in_millimeters():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # millimeters
    assert meters_to_drawing_units(doc, 2.0) == 2000.0


def test_meters_when_units_unset():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 0  # unitless -> assume drawing units == meters
    assert meters_to_drawing_units(doc, 2.0) == 2.0


def test_current_units(sample_doc):
    assert current_units(sample_doc["doc"]) == "m"  # fixture is $INSUNITS=6


def test_set_units_changes_conversion(sample_doc):
    doc = sample_doc["doc"]
    set_units(doc, "mm")
    assert current_units(doc) == "mm"
    assert meters_to_drawing_units(doc, 2.0) == 2000.0


def test_set_units_rejects_unknown(sample_doc):
    with pytest.raises(ValueError):
        set_units(sample_doc["doc"], "furlongs")
