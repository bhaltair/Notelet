from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI

from tracing import JsonlTracer
from tools import TOOLS, run_tool


ENV_PATH = Path(__file__).with_name(".env")
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
MAX_TOOL_ROUNDS = 4
EventHandler = Callable[[dict[str, Any]], None]
SYSTEM_PROMPT = (
    "You are a concise CLI notes assistant. "
    "Use add_note when the user asks you to remember or save something. "
    "Use search_notes when the user asks for specific saved information. "
    "Use list_recent_notes or read_notes when the user asks what has been saved. "
    "Only claim a note was saved after the add_note tool succeeds."
)


def run_agent_turn(
    client: OpenAI,
    messages: list[dict[str, Any]],
    user_text: str,
    model: str | None = None,
    on_tool_event: EventHandler | None = None,
    on_event: EventHandler | None = None,
) -> str:
    model = model or default_model()
    user_message = {"role": "user", "content": user_text}
    _emit_event(on_event, {"type": "user_message", "content": user_text})
    chat_messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *messages,
        user_message,
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        completion = client.chat.completions.create(
            model=model,
            messages=chat_messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        message = completion.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        _emit_event(
            on_event,
            {
                "type": "model_response",
                "model": model,
                "content": getattr(message, "content", None),
                "tool_call_count": len(tool_calls),
            },
        )

        if not tool_calls:
            answer = (getattr(message, "content", None) or "").strip()
            messages.extend([user_message, {"role": "assistant", "content": answer}])
            _emit_event(on_event, {"type": "final_answer", "content": answer})
            return answer

        chat_messages.append(_assistant_tool_call_message(message, tool_calls))
        for tool_call in tool_calls:
            chat_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": _execute_tool_call(tool_call, on_tool_event, on_event),
                }
            )

    raise RuntimeError("The agent reached the maximum number of tool rounds.")


def default_model() -> str:
    return os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL


def load_dotenv(env_path: Path = ENV_PATH) -> None:
    if not env_path.exists():
        return

    # Existing shell values win so PowerShell can temporarily override .env.
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def _assistant_tool_call_message(
    message: Any,
    tool_calls: list[Any],
) -> dict[str, Any]:
    # Chat Completions expects assistant tool calls before matching tool results.
    return {
        "role": "assistant",
        "content": getattr(message, "content", None),
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in tool_calls
        ],
    }


def _execute_tool_call(
    tool_call: Any,
    on_tool_event: EventHandler | None = None,
    on_event: EventHandler | None = None,
) -> str:
    name = tool_call.function.name
    is_error = False
    try:
        arguments = json.loads(tool_call.function.arguments or "{}")
        event = {"type": "tool_call", "name": name, "arguments": arguments}
        _emit_event(on_tool_event, event)
        _emit_event(on_event, event)
        output = run_tool(name, arguments)
    except Exception as exc:
        is_error = True
        output = f"Tool error: {exc}"
        event = {"type": "tool_error", "name": name, "message": str(exc)}
        _emit_event(on_tool_event, event)
        _emit_event(on_event, event)

    event = {"type": "tool_result", "name": name, "output": output, "is_error": is_error}
    _emit_event(on_tool_event, event)
    _emit_event(on_event, event)
    return output


def _emit_event(
    on_event: EventHandler | None,
    event: dict[str, Any],
) -> None:
    if on_event is not None:
        on_event(event)


def print_tool_event(event: dict[str, Any]) -> None:
    if event["type"] == "tool_call":
        arguments = json.dumps(event["arguments"], ensure_ascii=False)
        print(f"Tool call: {event['name']}({arguments})")
    elif event["type"] == "tool_error":
        print(f"Tool error: {event['message']}")
    elif event["type"] == "tool_result" and not event.get("is_error"):
        print(f"Tool result: {event['output']}")


def build_cli_event_handler(tracer: JsonlTracer) -> EventHandler:
    def handle_event(event: dict[str, Any]) -> None:
        tracer.record(event)
        print_tool_event(event)

    return handle_event


def main() -> None:
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY before running the agent.")

    client = OpenAI()
    tracer = JsonlTracer()
    messages: list[dict[str, Any]] = []

    print("Simple Notes Agent. Type 'exit' or 'quit' to stop.")
    while True:
        user_text = input("You> ").strip()
        if user_text.lower() in {"exit", "quit"}:
            break
        if not user_text:
            continue

        try:
            answer = run_agent_turn(
                client,
                messages,
                user_text,
                on_event=build_cli_event_handler(tracer),
            )
        except Exception as exc:
            tracer.record({"type": "agent_error", "message": str(exc)})
            answer = f"Agent error: {exc}"

        print(f"Agent> {answer}")


if __name__ == "__main__":
    main()
