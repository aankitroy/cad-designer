import io
import uuid

import ezdxf
from ezdxf.document import Drawing


class SessionStore:
    def __init__(self) -> None:
        self._docs: dict[str, Drawing] = {}
        self._history: dict[str, list[str]] = {}

    def create(self, dxf_bytes: bytes) -> str:
        try:
            doc = ezdxf.read(io.StringIO(dxf_bytes.decode("utf-8", errors="replace")))
        except Exception as e:  # ezdxf.DXFStructureError and friends
            raise ValueError(f"Not a valid DXF file: {e}") from e
        sid = uuid.uuid4().hex
        self._docs[sid] = doc
        self._history[sid] = []
        return sid

    def get(self, sid: str) -> Drawing | None:
        return self._docs.get(sid)

    def snapshot(self, sid: str) -> None:
        doc = self._docs[sid]
        buf = io.StringIO()
        doc.write(buf)
        self._history[sid].append(buf.getvalue())

    def undo(self, sid: str) -> bool:
        history = self._history.get(sid) or []
        if not history:
            return False
        snap = history.pop()
        self._docs[sid] = ezdxf.read(io.StringIO(snap))
        return True

    def serialize(self, sid: str) -> bytes:
        buf = io.StringIO()
        self._docs[sid].write(buf)
        return buf.getvalue().encode("utf-8")
