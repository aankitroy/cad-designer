import os
import re
from pathlib import Path

LIBRARY_DIR = os.environ.get(
    "CAD_LIBRARY_DIR",
    str(Path.home() / "Downloads" / "BASE_LIBRARY_components"),
)


def _slug(stem: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-").lower() or "component"


def _catalog(directory: str) -> dict[str, str]:
    """Ordered {id: filename} for the .dxf files in directory; ids unique + stable."""
    d = Path(directory)
    if not d.is_dir():
        return {}
    out: dict[str, str] = {}
    for path in sorted(d.glob("*.dxf"), key=lambda p: p.stem.lower()):
        base = _slug(path.stem)
        cid, i = base, 2
        while cid in out:
            cid = f"{base}-{i}"
            i += 1
        out[cid] = path.name
    return out


def list_components(directory: str = LIBRARY_DIR) -> list[dict]:
    return [
        {"id": cid, "name": Path(fn).stem} for cid, fn in _catalog(directory).items()
    ]


def component_path(cid: str, directory: str = LIBRARY_DIR) -> str | None:
    fn = _catalog(directory).get(cid)
    if fn is None:
        return None
    return str(Path(directory) / fn)
