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


def test_selectables_lists_added_excludes_base(sample_bytes, monkeypatch):
    _fresh_store()
    sid = main.store.create(sample_bytes)

    # base-shell WALLS polyline (present before any session edit) must stay locked
    base_wall = next(
        e.dxf.handle for e in main.store.get(sid).modelspace() if e.dxf.layer == "WALLS"
    )

    def fake_run_agent(**kwargs):
        from app import edits

        c = edits.add_wall(kwargs["doc"], 0, 0, 3, 0, layer="NEW")
        return {"reply": "added", "changes": [c], "entrance": None}

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    monkeypatch.setattr(main, "_anthropic_client", lambda: object())
    r = client.post(f"/sessions/{sid}/chat", data={"message": "add a wall"})
    added_handle = r.json()["changes"][0]["handle"]

    s = client.get(f"/sessions/{sid}/selectables")
    assert s.status_code == 200
    body = s.json()
    handles = {e["handle"] for e in body["selectables"]}
    assert added_handle in handles
    assert base_wall not in handles  # base shell is locked
    assert body["view"] is not None
    one = next(e for e in body["selectables"] if e["handle"] == added_handle)
    assert len(one["bbox"]) == 4 and "label" in one


def test_edit_move_converts_meters_and_returns_view(sample_bytes):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    from app import edits

    c = edits.add_wall(main.store.get(sid), 2, 2, 4, 2, layer="NEW")
    main._editable.setdefault(sid, set()).add(c["handle"])
    h = c["handle"]

    r = client.post(
        f"/sessions/{sid}/edit",
        json={"name": "move_entity", "args": {"handle": h, "dx_m": 1.0, "dy_m": 0.0}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["change"]["op"] == "move_entity"
    assert body["view"] is not None and "selectables" in body
    moved = main.store.get(sid).entitydb[h]
    first_x = list(moved.get_points())[0][0]
    assert abs(first_x - 3.0) < 1e-6  # was 2, +1m (meters fixture)


def test_edit_delete_drops_from_selectables(sample_bytes):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    from app import edits

    c = edits.add_wall(main.store.get(sid), 0, 0, 1, 1, layer="NEW")
    main._editable.setdefault(sid, set()).add(c["handle"])
    h = c["handle"]
    r = client.post(
        f"/sessions/{sid}/edit", json={"name": "delete_entity", "args": {"handle": h}}
    )
    assert r.status_code == 200
    assert all(e["handle"] != h for e in r.json()["selectables"])


def test_edit_rejects_unknown_op(sample_bytes):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    r = client.post(f"/sessions/{sid}/edit", json={"name": "frobnicate", "args": {}})
    assert r.status_code == 400


def test_edit_bad_handle_is_422_and_no_change(sample_bytes):
    _fresh_store()
    sid = main.store.create(sample_bytes)
    before = len(list(main.store.get(sid).modelspace()))
    r = client.post(
        f"/sessions/{sid}/edit",
        json={"name": "move_entity", "args": {"handle": "DEAD", "dx_m": 1, "dy_m": 0}},
    )
    assert r.status_code == 422
    assert len(list(main.store.get(sid).modelspace())) == before


def test_upload_and_undo_include_view(sample_bytes):
    _fresh_store()
    up = client.post(
        "/sessions",
        files={"file": ("plan.dxf", io.BytesIO(sample_bytes), "application/dxf")},
    )
    assert up.json()["view"] is not None
    sid = up.json()["session_id"]
    un = client.post(f"/sessions/{sid}/undo")
    assert "view" in un.json()


def _lib_dir(tmp_path):
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.modelspace().add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    doc.saveas(tmp_path / "CHAIR UNIT.dxf")
    return str(tmp_path)


def test_library_catalog(tmp_path, monkeypatch):
    from app import library

    monkeypatch.setattr(library, "LIBRARY_DIR", _lib_dir(tmp_path))
    r = client.get("/library")
    assert r.status_code == 200
    comps = r.json()["components"]
    assert any(c["name"] == "CHAIR UNIT" for c in comps)


def test_library_thumbnail_cached(tmp_path, monkeypatch):
    from app import library
    from app import main as main_mod

    monkeypatch.setattr(library, "LIBRARY_DIR", _lib_dir(tmp_path))
    main_mod._thumb_cache.clear()
    calls = {"n": 0}
    real = main_mod.render_svg

    def counting(doc):
        calls["n"] += 1
        return real(doc)

    monkeypatch.setattr(main_mod, "render_svg", counting)
    cid = client.get("/library").json()["components"][0]["id"]
    r1 = client.get(f"/library/{cid}/thumbnail.svg")
    r2 = client.get(f"/library/{cid}/thumbnail.svg")
    assert r1.status_code == 200 and "svg" in r1.text[:200].lower()
    assert r2.status_code == 200
    assert calls["n"] == 1  # second call served from cache


def test_library_thumbnail_unknown(tmp_path, monkeypatch):
    from app import library

    monkeypatch.setattr(library, "LIBRARY_DIR", _lib_dir(tmp_path))
    assert client.get("/library/nope/thumbnail.svg").status_code == 404


def test_library_place_imports_once_and_centers(sample_bytes, tmp_path, monkeypatch):
    from app import library

    monkeypatch.setattr(library, "LIBRARY_DIR", _lib_dir(tmp_path))
    _fresh_store()
    sid = main.store.create(sample_bytes)
    cid = client.get("/library").json()["components"][0]["id"]

    r = client.post(
        f"/sessions/{sid}/library/place",
        json={"id": cid, "x_m": 5.0, "y_m": 4.0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["change"]["op"] == "place_component"
    assert any(s["handle"] == body["change"]["handle"] for s in body["selectables"])
    assert body["view"] is not None

    n_blocks = len(list(main.store.get(sid).blocks))
    client.post(f"/sessions/{sid}/library/place", json={"id": cid, "x_m": 1, "y_m": 1})
    assert len(list(main.store.get(sid).blocks)) == n_blocks  # no new block def


def test_library_place_unknown_id(sample_bytes, tmp_path, monkeypatch):
    from app import library

    monkeypatch.setattr(library, "LIBRARY_DIR", _lib_dir(tmp_path))
    _fresh_store()
    sid = main.store.create(sample_bytes)
    r = client.post(
        f"/sessions/{sid}/library/place", json={"id": "ghost", "x_m": 0, "y_m": 0}
    )
    assert r.status_code == 404


def test_library_place_unknown_session(sample_bytes, tmp_path, monkeypatch):
    from app import library

    monkeypatch.setattr(library, "LIBRARY_DIR", _lib_dir(tmp_path))
    _fresh_store()
    main.store.create(sample_bytes)
    cid = client.get("/library").json()["components"][0]["id"]
    r = client.post(
        "/sessions/nosuch/library/place", json={"id": cid, "x_m": 0, "y_m": 0}
    )
    assert r.status_code == 404
