import io

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.sessions import SessionStore

client = TestClient(app)


def _fresh_store():
    main.store = SessionStore()  # reset between tests


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_upload_returns_session_and_svg(sample_bytes):
    _fresh_store()
    r = client.post(
        "/sessions",
        files={"file": ("plan.dxf", io.BytesIO(sample_bytes), "application/dxf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body and body["svg"].lstrip().startswith("<")
    assert any(l["name"] == "WALLS" for l in body["summary"]["layers"])


def test_upload_rejects_garbage():
    _fresh_store()
    r = client.post(
        "/sessions",
        files={"file": ("x.dxf", io.BytesIO(b"nope"), "application/dxf")},
    )
    assert r.status_code == 422


def test_chat_applies_edit_and_rerenders(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)

    def fake_run_agent(**kwargs):
        c = edits.add_wall(kwargs["doc"], 0, 0, 3, 0)
        return {"reply": "Added a wall.", "changes": [c]}

    from app import edits

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())

    r = client.post(f"/sessions/{sid}/chat", data={"message": "add a wall"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "Added a wall."
    assert body["changes"][0]["op"] == "add_wall"
    assert body["svg"].lstrip().startswith("<")


def test_chat_with_attachment_imports_and_exposes_component(
    sample_bytes, component_bytes, monkeypatch
):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    seen = {}

    def fake_run_agent(**kwargs):
        seen["components"] = kwargs.get("components")
        from app import edits

        name = kwargs["components"][0]
        c = edits.place_component(kwargs["doc"], name, 0, 0)
        return {"reply": "placed", "changes": [c]}

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())

    r = client.post(
        f"/sessions/{sid}/chat",
        data={"message": "place the chair by the door"},
        files={"file": ("chair.dxf", io.BytesIO(component_bytes), "application/dxf")},
    )
    assert r.status_code == 200
    assert seen["components"] == ["chair"]
    assert r.json()["changes"][0]["op"] == "place_component"


def test_chat_without_attachment_still_works(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    monkeypatch.setattr(main, "run_agent", lambda **k: {"reply": "ok", "changes": []})
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())
    r = client.post(f"/sessions/{sid}/chat", data={"message": "hi"})
    assert r.status_code == 200


def test_chat_rejects_bad_attachment(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())
    r = client.post(
        f"/sessions/{sid}/chat",
        data={"message": "place this"},
        files={"file": ("x.dxf", io.BytesIO(b"junk"), "application/dxf")},
    )
    assert r.status_code == 422


def test_undo_endpoint(sample_bytes):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    before = len(list(main.store.get(sid).modelspace()))
    main.store.snapshot(sid)
    from app import edits

    edits.add_wall(main.store.get(sid), 0, 0, 1, 1)

    r = client.post(f"/sessions/{sid}/undo")
    assert r.status_code == 200
    assert len(list(main.store.get(sid).modelspace())) == before


def test_upload_summary_includes_units(sample_bytes):
    _fresh_store()
    r = client.post(
        "/sessions",
        files={"file": ("plan.dxf", io.BytesIO(sample_bytes), "application/dxf")},
    )
    body = r.json()
    assert body["summary"]["units"] == "m"  # fixture is $INSUNITS=6
    assert "mm" in body["summary"]["unit_options"]


def test_set_units_endpoint(sample_bytes):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    r = client.post(f"/sessions/{sid}/units", json={"units": "mm"})
    assert r.status_code == 200
    assert r.json()["units"] == "mm"
    assert int(main.store.get(sid).header["$INSUNITS"]) == 4  # mm


def test_set_units_rejects_unknown(sample_bytes):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    r = client.post(f"/sessions/{sid}/units", json={"units": "furlongs"})
    assert r.status_code == 422


def test_download_dxf(sample_bytes):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    r = client.get(f"/sessions/{sid}/dxf")
    assert r.status_code == 200
    assert b"SECTION" in r.content  # DXF marker


def test_chat_passes_frame_text_to_agent(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    seen = {}

    def fake_run_agent(**kwargs):
        seen["frame_text"] = kwargs.get("frame_text")
        return {"reply": "ok", "changes": [], "entrance": None}

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())
    r = client.post(f"/sessions/{sid}/chat", data={"message": "where is the back?"})
    assert r.status_code == 200
    assert "back_center" in (seen["frame_text"] or "")


def test_chat_persists_entrance_override(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)

    def fake_run_agent(**kwargs):
        return {"reply": "set", "changes": [], "entrance": "north"}

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())
    client.post(f"/sessions/{sid}/chat", data={"message": "entrance is at the top"})
    assert main._orientation.get(sid) == "north"

    captured = {}

    def fake_run_agent2(**kwargs):
        captured["frame_text"] = kwargs.get("frame_text")
        return {"reply": "ok", "changes": [], "entrance": None}

    monkeypatch.setattr(main, "run_agent", fake_run_agent2)
    client.post(f"/sessions/{sid}/chat", data={"message": "now where is the front?"})
    assert "front=max_y" in (captured["frame_text"] or "")
