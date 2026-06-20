"""Bridge to the read-only lenskart-store-design skill scripts/assets.
All store-layout-ai modules import skill APIs from HERE, never by reaching in directly."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SKILL = os.path.join(REPO, "lenskart-store-design")
SCRIPTS = os.path.join(SKILL, "scripts")
ASSETS = os.path.join(SKILL, "assets")
BASE_FILES = os.path.join(REPO, "fine-tuning", "BASE FILES")

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from dxf_engine import (  # noqa: E402
    load_shell, import_library, import_clinic_rooms, render_png, Placer,
    SINK_ROOM_BLOCK, RO_ROOM_BLOCK,
)
from extract_shell import extract_structure  # noqa: E402
from audit import audit, print_report  # noqa: E402
from clinic_arrangements import place_arrangement, ARRANGEMENTS  # noqa: E402

__all__ = [
    "load_shell", "import_library", "import_clinic_rooms", "render_png", "Placer",
    "SINK_ROOM_BLOCK", "RO_ROOM_BLOCK", "extract_structure", "audit", "print_report",
    "place_arrangement", "ARRANGEMENTS", "SKILL", "ASSETS", "SCRIPTS", "BASE_FILES", "REPO",
]
