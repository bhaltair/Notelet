from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

from flask import Flask, Response, jsonify, render_template, request
from openai import OpenAI

from agent import default_model, load_dotenv, run_agent_turn, stream_agent_turn
from tools import list_recent_notes, search_notes
from tracing import JsonlTracer


def create_app(
    client: OpenAI | None = None,
    messages: list[dict[str, Any]] | None = None,
    tracer: JsonlTracer | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["NOTELET_CLIENT"] = client
    app.config["NOTELET_MESSAGES"] = messages if messages is not None else []
    app.config["NOTELET_TRACER"] = tracer

    @app.get("/")
    def index() -> str:
        return render_template("index.html", model=default_model())

    @app.get("/health")
    def health() -> tuple[Any, int]:
        return jsonify({"ok": True, "model": default_model()}), 200

    @app.post("/api/chat")
    def chat() -> tuple[Any, int]:
        message, error_response = _request_message()
        if error_response is not None:
            return error_response

        events: list[dict[str, Any]] = []

        def record_event(event: dict[str, Any]) -> None:
            events.append(event)
            _record_trace(app, event)

        try:
            answer = run_agent_turn(
                _runtime_client(app),
                app.config["NOTELET_MESSAGES"],
                message,
                on_event=record_event,
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

        return jsonify({"answer": answer, "events": events}), 200

    @app.post("/api/chat/stream")
    def chat_stream() -> Response | tuple[Any, int]:
        message, error_response = _request_message()
        if error_response is not None:
            return error_response

        def generate() -> Iterator[str]:
            try:
                for event in stream_agent_turn(
                    _runtime_client(app),
                    app.config["NOTELET_MESSAGES"],
                    message,
                    on_event=lambda event: _record_trace(app, event),
                ):
                    yield _sse(event["type"], event)
            except Exception as exc:
                event = {"type": "error", "message": str(exc)}
                _record_trace(app, event)
                yield _sse("error", event)

        return Response(generate(), mimetype="text/event-stream")

    @app.get("/api/notes")
    def notes() -> tuple[Any, int]:
        query = request.args.get("q", "").strip()
        if query:
            notes_text = search_notes(query)
        else:
            notes_text = list_recent_notes()
        return jsonify({"notes": notes_text}), 200

    return app


def _request_message() -> tuple[str, tuple[Any, int] | None]:
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    if not isinstance(message, str) or not message.strip():
        return "", (jsonify({"error": "message is required"}), 400)
    return message.strip(), None


def _runtime_client(app: Flask) -> OpenAI:
    client = app.config.get("NOTELET_CLIENT")
    if client is not None:
        return client

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY before using the API.")

    client = OpenAI()
    app.config["NOTELET_CLIENT"] = client
    return client


def _record_trace(app: Flask, event: dict[str, Any]) -> None:
    tracer = app.config.get("NOTELET_TRACER")
    if tracer is not None:
        tracer.record(event)


def _sse(event_name: str, event: dict[str, Any]) -> str:
    data = json.dumps(event, ensure_ascii=False)
    return f"event: {event_name}\ndata: {data}\n\n"


def main() -> None:
    load_dotenv()
    app = create_app(tracer=JsonlTracer())
    app.run(host="127.0.0.1", port=5000, debug=True)


if __name__ == "__main__":
    main()
