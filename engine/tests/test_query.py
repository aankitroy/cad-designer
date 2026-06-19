from app.query import list_layers, query_entities


def test_list_layers(sample_doc):
    layers = list_layers(sample_doc["doc"])
    names = {l["name"] for l in layers}
    assert {"WALLS", "FIXTURES", "TEXT"} <= names


def test_query_by_layer(sample_doc):
    results = query_entities(sample_doc["doc"], layer="WALLS")
    assert any(e["handle"] == sample_doc["wall_handle"] for e in results)
    assert all(e["layer"] == "WALLS" for e in results)


def test_query_by_near_text(sample_doc):
    results = query_entities(sample_doc["doc"], near_text="cash")
    assert any("CASH" in (e.get("text") or "").upper() for e in results)


def test_query_returns_handles_and_types(sample_doc):
    results = query_entities(sample_doc["doc"])
    sample = results[0]
    assert "handle" in sample and "type" in sample and "layer" in sample
