import ezdxf

from app.units import meters_to_drawing_units


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
