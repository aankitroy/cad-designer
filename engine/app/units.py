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

# friendly name <-> $INSUNITS code (the subset we expose in the UI)
_CODE_BY_NAME = {"unitless": 0, "in": 1, "ft": 2, "mm": 4, "cm": 5, "m": 6}
_NAME_BY_CODE = {code: name for name, code in _CODE_BY_NAME.items()}

# order shown in the UI selector
UNIT_NAMES = ["mm", "cm", "m", "in", "ft", "unitless"]


def meters_to_drawing_units(doc: Drawing, meters: float) -> float:
    code = int(doc.header.get("$INSUNITS", 0))
    mpu = _METERS_PER_UNIT.get(code, 1.0)
    return meters / mpu


def current_units(doc: Drawing) -> str:
    """Friendly name for the doc's current $INSUNITS (defaults to 'unitless')."""
    code = int(doc.header.get("$INSUNITS", 0))
    return _NAME_BY_CODE.get(code, "unitless")


def set_units(doc: Drawing, name: str) -> None:
    """Override the doc's drawing units. Raises ValueError on an unknown name."""
    if name not in _CODE_BY_NAME:
        raise ValueError(f"Unknown units {name!r}; expected one of {UNIT_NAMES}")
    doc.header["$INSUNITS"] = _CODE_BY_NAME[name]
