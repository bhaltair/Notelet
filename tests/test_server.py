from types import SimpleNamespace

import server


class FakeChatCompletions:
    def __init__(self, completions):
        self._completions = list(completions)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._completions.pop(0)


class FakeChat:
    def __init__(self, completions):
        self.completions = FakeChatCompletions(completions)


class FakeChatClient:
    def __init__(self, completions):
        self.chat = FakeChat(completions)


def make_completion(content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=tool_calls)
            )
        ]
    )


def make_stream_chunk(content=None):
    return {"choices": [{"delta": {"content": content}}]}


def test_chat_endpoint_returns_answer_and_events():
    client = FakeChatClient([make_completion(content="Hello there.")])
    app = server.create_app(client=client)

    response = app.test_client().post("/api/chat", json={"message": "Hello"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["answer"] == "Hello there."
    assert [event["type"] for event in payload["events"]] == [
        "user_message",
        "model_response",
        "final_answer",
    ]


def test_index_explains_frontend_dev_server_when_dist_is_missing(tmp_path):
    missing_dist = tmp_path / "missing"
    app = server.create_app(client=FakeChatClient([]), frontend_dist=missing_dist)

    response = app.test_client().get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Notelet API Server" in body
    assert "npm.cmd run dev" in body


def test_index_serves_built_react_frontend(tmp_path):
    (tmp_path / "index.html").write_text("built frontend", encoding="utf-8")
    app = server.create_app(client=FakeChatClient([]), frontend_dist=tmp_path)

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "built frontend"


def test_frontend_assets_serves_built_assets(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('hi')", encoding="utf-8")
    app = server.create_app(client=FakeChatClient([]), frontend_dist=tmp_path)

    response = app.test_client().get("/assets/app.js")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "console.log('hi')"


def test_chat_endpoint_rejects_empty_message():
    app = server.create_app(client=FakeChatClient([]))

    response = app.test_client().post("/api/chat", json={"message": "   "})

    assert response.status_code == 400
    assert response.get_json() == {"error": "message is required"}


def test_stream_endpoint_emits_sse_events():
    client = FakeChatClient(
        [
            [
                make_stream_chunk("Saved"),
                make_stream_chunk(" it."),
            ]
        ]
    )
    app = server.create_app(client=client)

    response = app.test_client().post(
        "/api/chat/stream",
        json={"message": "Remember this"},
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert "event: answer_delta" in body
    assert 'data: {"type": "answer_delta", "content": "Saved"}' in body
    assert "event: final_answer" in body
    assert client.chat.completions.calls[0]["stream"] is True


def test_notes_endpoint_returns_recent_notes(monkeypatch):
    monkeypatch.setattr(server, "list_recent_notes", lambda: "- saved note")

    app = server.create_app(client=FakeChatClient([]))
    response = app.test_client().get("/api/notes")

    assert response.status_code == 200
    assert response.get_json() == {"notes": "- saved note"}


def test_notes_endpoint_searches_when_query_is_present(monkeypatch):
    calls = []

    def fake_search_notes(query):
        calls.append(query)
        return "- matching note"

    monkeypatch.setattr(server, "search_notes", fake_search_notes)

    app = server.create_app(client=FakeChatClient([]))
    response = app.test_client().get("/api/notes?q=agent")

    assert response.status_code == 200
    assert response.get_json() == {"notes": "- matching note"}
    assert calls == ["agent"]


def test_sse_formats_json_events():
    event = {"type": "answer_delta", "content": "hi"}

    assert server._sse("answer_delta", event) == (
        'event: answer_delta\ndata: {"type": "answer_delta", "content": "hi"}\n\n'
    )
