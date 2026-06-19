from ezdxf.document import Drawing

# $INSUNITS code -> meters per drawing unit
_METERS_PER_UNIT = {
    0: 1.0,      # unitless: assume meters
    1: 0.0254,   # inches
    2: 0.3048,   # feet
    4: 0.001,    # millimeters
    5: 0.01,     # centimeters
    6: 1.0,      # meters
}


def meters_to_drawing_units(doc: Drawing, meters: float) -> float:
    code = int(doc.header.get("$INSUNITS", 0))
    mpu = _METERS_PER_UNIT.get(code, 1.0)
    return meters / mpu
