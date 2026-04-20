from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request, send_from_directory
from openai import OpenAI

from agent import default_model, load_dotenv, run_agent_turn, stream_agent_turn
from tools import list_recent_notes, search_notes
from tracing import JsonlTracer


FRONTEND_DIST = Path(__file__).with_name("frontend") / "dist"


def create_app(
    client: OpenAI | None = None,
    messages: list[dict[str, Any]] | None = None,
    tracer: JsonlTracer | None = None,
    frontend_dist: Path | None = FRONTEND_DIST,
) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["NOTELET_CLIENT"] = client
    app.config["NOTELET_MESSAGES"] = messages if messages is not None else []
    app.config["NOTELET_TRACER"] = tracer
    app.config["NOTELET_FRONTEND_DIST"] = frontend_dist

    @app.get("/")
    def index() -> Response | str:
        dist = app.config["NOTELET_FRONTEND_DIST"]
        if dist is not None and (dist / "index.html").exists():
            return send_from_directory(dist, "index.html")
        return _frontend_dev_message()

    @app.get("/assets/<path:filename>")
    def frontend_assets(filename: str) -> Response | tuple[Any, int]:
        dist = app.config["NOTELET_FRONTEND_DIST"]
        assets_dir = dist / "assets" if dist is not None else None
        if assets_dir is None or not assets_dir.exists():
            return jsonify({"error": "frontend build not found"}), 404
        return send_from_directory(assets_dir, filename)

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
            # 端到端 streaming 的第二段：agent.stream_agent_turn 产出 Python dict 事件。
            # Flask 不能直接把 dict 发给浏览器，所以这里逐个转成 SSE 文本帧：
            # event: <事件名>
            # data: <JSON 字符串>
            #
            # 浏览器收到的是连续字节流，前端会按空行拆回一个个事件。
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
                print(f"SSE send: error {event}")
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
    # SSE 协议是纯文本格式。每个事件用空行结尾。
    # event 行给事件分类；data 行放 JSON payload，前端只解析 data 行。
    # ensure_ascii=False 让中文内容在浏览器调试和 trace 中保持可读。
    data = json.dumps(event, ensure_ascii=False)
    print(f"SSE frame encoded: event={event_name} data={data}")
    return f"event: {event_name}\ndata: {data}\n\n"


def _frontend_dev_message() -> str:
    return """
    <!doctype html>
    <title>Notelet API Server</title>
    <h1>Notelet API Server</h1>
    <p>The React/Vite frontend has not been built yet.</p>
    <p>For development, run <code>npm.cmd run dev</code> inside
    <code>frontend/</code> and open <code>http://127.0.0.1:5173</code>.</p>
    <p>To serve the built app from Flask, run <code>npm.cmd run build</code>
    inside <code>frontend/</code>, then restart this server.</p>
    """


def main() -> None:
    load_dotenv()
    app = create_app(tracer=JsonlTracer())
    app.run(host="127.0.0.1", port=5000, debug=True)


if __name__ == "__main__":
    main()
