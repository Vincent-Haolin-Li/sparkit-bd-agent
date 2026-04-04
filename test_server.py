from fastapi.testclient import TestClient

import server


def test_run_endpoint_streams_legacy_events(monkeypatch):
    class FakeGraph:
        async def astream(self, initial_state, stream_mode="updates", config=None):
            assert initial_state == {"brief": "find partners", "n": 2}
            assert stream_mode == "updates"
            assert config == {"recursion_limit": 200}
            yield {"search": {"events": [{"event": "search_done", "data": {"count": 1, "candidates": [{"title": "Alpha", "url": "https://alpha.test"}]}}]}}
            yield {"research": {"events": [{"event": "researching", "data": {"index": 1, "title": "Alpha", "url": "https://alpha.test"}}]}}
            yield {"done": {"events": [{"event": "done", "data": {"result": {"summary": {"total_targets": 1, "top_target": "Alpha"}}, "saved_to": "output/test.json"}}]}}

    monkeypatch.setattr(server, "BD_GRAPH", FakeGraph())
    client = TestClient(server.app)

    with client.stream("GET", "/run", params={"brief": "find partners", "n": 2}) as response:
        body = b"".join(response.iter_bytes()).decode("utf-8")

    assert response.status_code == 200
    assert '"event": "searching"' in body
    assert '"event": "search_done"' in body
    assert '"event": "researching"' in body
    assert '"event": "done"' in body


def test_run_endpoint_uses_n_targets_when_given(monkeypatch):
    class FakeGraph:
        async def astream(self, initial_state, stream_mode="updates", config=None):
            assert initial_state == {"brief": "find partners", "n": 1}
            yield {"done": {"events": [{"event": "done", "data": {"result": {"summary": {"total_targets": 0, "top_target": ""}}, "saved_to": "output/test.json"}}]}}

    monkeypatch.setattr(server, "BD_GRAPH", FakeGraph())
    client = TestClient(server.app)

    with client.stream("GET", "/run", params={"brief": "find partners", "n": 5, "n_targets": 1}) as response:
        body = b"".join(response.iter_bytes()).decode("utf-8")

    assert response.status_code == 200
    assert '"event": "searching"' in body
    assert '"n": 1' in body
    assert '"event": "done"' in body


def test_run_endpoint_streams_error_event(monkeypatch):
    class FakeGraph:
        async def astream(self, initial_state, stream_mode="updates", config=None):
            raise RuntimeError("graph exploded")
            yield

    monkeypatch.setattr(server, "BD_GRAPH", FakeGraph())
    client = TestClient(server.app)

    with client.stream("GET", "/run", params={"brief": "find partners", "n": 2}) as response:
        body = b"".join(response.iter_bytes()).decode("utf-8")

    assert response.status_code == 200
    assert '"event": "searching"' in body
    assert '"event": "error"' in body
    assert "graph exploded" in body


def test_run_endpoint_requires_brief():
    client = TestClient(server.app)
    response = client.get("/run")
    assert response.json() == {"error": "brief required"}
