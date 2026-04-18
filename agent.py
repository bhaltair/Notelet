from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from tools import TOOLS, run_tool


DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
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
    model: str = DEFAULT_MODEL,
) -> str:
    user_message = {"role": "user", "content": user_text}
    input_items: list[dict[str, Any]] = [*messages, user_message]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            tools=TOOLS,
            input=input_items,
            parallel_tool_calls=False,
        )
        tool_calls = [
            item for item in response.output if getattr(item, "type", None) == "function_call"
        ]

        if not tool_calls:
            answer = response.output_text.strip()
            messages.extend([user_message, {"role": "assistant", "content": answer}])
            return answer

        for tool_call in tool_calls:
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": _execute_tool_call(tool_call),
                }
            )

    raise RuntimeError("The agent reached the maximum number of tool rounds.")


def _execute_tool_call(tool_call: Any) -> str:
    try:
        arguments = json.loads(tool_call.arguments or "{}")
        return run_tool(tool_call.name, arguments)
    except Exception as exc:
        return f"Tool error: {exc}"


def main() -> None:
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
