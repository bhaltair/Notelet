from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from tools import TOOLS, run_tool


ENV_PATH = Path(__file__).with_name(".env")
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
MAX_TOOL_ROUNDS = 4
SYSTEM_PROMPT = (
    "You are a concise CLI notes assistant. "
    "Use add_note when the user asks you to remember or save something. "
    "Use read_notes when the user asks what has been saved. "
    "Only claim a note was saved after the add_note tool succeeds."
)


def run_agent_turn(
    client: OpenAI,
    messages: list[dict[str, Any]],
    user_text: str,
    model: str | None = None,
) -> str:
    model = model or default_model()
    user_message = {"role": "user", "content": user_text}

    # Chat Completions 同时适用于 OpenAI 和 DeepSeek，避免维护两套工具调用循环。
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

        if not tool_calls:
            answer = (getattr(message, "content", None) or "").strip()
            messages.extend([user_message, {"role": "assistant", "content": answer}])
            return answer

        chat_messages.append(_assistant_tool_call_message(message, tool_calls))
        for tool_call in tool_calls:
            chat_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": _execute_tool_call(tool_call),
                }
            )

    raise RuntimeError("The agent reached the maximum number of tool rounds.")


def default_model() -> str:
    return os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL


def load_dotenv(env_path: Path = ENV_PATH) -> None:
    if not env_path.exists():
        return

    # 已有的 shell 环境变量优先，方便用 PowerShell 临时覆盖 .env 配置。
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
    # Chat Completions 要求顺序是：assistant 调用工具，然后 tool 返回结果。
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


def _execute_tool_call(tool_call: Any) -> str:
    try:
        arguments = json.loads(tool_call.function.arguments or "{}")
        return run_tool(tool_call.function.name, arguments)
    except Exception as exc:
        return f"Tool error: {exc}"


def main() -> None:
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY before running the agent.")

    client = OpenAI()
    messages: list[dict[str, Any]] = []

    print("Simple Notes Agent. Type 'exit' or 'quit' to stop.")
    while True:
        user_text = input("You> ").strip()
        if user_text.lower() in {"exit", "quit"}:
            break
        if not user_text:
            continue

        try:
            answer = run_agent_turn(client, messages, user_text)
        except Exception as exc:
            answer = f"Agent error: {exc}"

        print(f"Agent> {answer}")


if __name__ == "__main__":
    main()
