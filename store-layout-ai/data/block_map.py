"""Classify every block name found in an FP DXF into how the generated script should
represent it: a library place(), a substitution rect(), a clinic room, or skip (shell)."""
import os
import functools
import ezdxf
import skilllib

# Known shell / structure blocks that belong to the INPUT, not the layout output.
SHELL_BLOCKS = {"existignn csk", "chennai mugappair existignd", "awefera", "32r23",
                "Entrance Door"}

CLINIC_ROOMS = {skilllib.SINK_ROOM_BLOCK, skilllib.RO_ROOM_BLOCK}

# Fire-safety blocks → reverse-engineer emits placer.fire(cx, cy) (a circle on the FE layer).
FIRE_BLOCKS = {"Fire Extinguisher"}

# Real fixtures whose FP block name is a variant/typo of a current library block.
# Mapped to the nearest valid library block so the script places (and audits + counts) it.
ALIASES = {
    "Billing Counter 1350": "Billing Counter-1350",   # space vs hyphen
    "VC 1010": "VC HD 1010",
    "VC 1200": "VC HD 1010",
    "VC HD 1200": "VC HD 1010",
    "JJ 1200": "JJ SH 1200",
    "JJ 900": "JJ SH 900",
    "JJ SUPERHYBRID 1200": "JJ SH 1200",
    "JJ SUPERHYBRID 1010": "JJ SHD 1010",
    "JJ SEE THROUGH 900": "JJ STSH 900",
}

# Retired / non-library blocks → explicit substitution (rect on a layer, with a label).
SUBSTITUTIONS = {
    "55INCH": {"layer": "LK-TV SCREEN", "label": "TV 55"},
    "BLUE ZERO": {"layer": "LK-FF&E FLOOR", "label": "BLUE ZERO"},
}


@functools.lru_cache(maxsize=1)
def library_block_names():
    lib = ezdxf.readfile(os.path.join(skilllib.ASSETS, "BASE LIBRARY.dxf"))
    return frozenset(b.name for b in lib.blocks
                     if not b.name.startswith("*") and not b.name.startswith("_"))


def classify(name):
    """Return (kind, target). kind in {library, clinic_room, fire, substitute, skip, unmapped}."""
    if name in SHELL_BLOCKS:
        return "skip", None
    if name in CLINIC_ROOMS:
        return "clinic_room", name
    if name in FIRE_BLOCKS:
        return "fire", None
    if name in ALIASES:
        return "library", ALIASES[name]
    if name in library_block_names():
        return "library", name
    if name in SUBSTITUTIONS:
        return "substitute", SUBSTITUTIONS[name]
    return "unmapped", None


def coverage(names):
    out = {"library": [], "clinic_room": [], "fire": [], "substitute": [],
           "skip": [], "unmapped": []}
    for n in set(names):
        kind, _ = classify(n)
        out[kind].append(n)
    return out
