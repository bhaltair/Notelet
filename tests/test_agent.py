import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import agent


FIXTURES_PATH = Path(__file__).with_name("fixtures")


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


def make_tool_call(name, arguments, call_id="call_123"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def make_completion(content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=tool_calls)
            )
        ]
    )


def test_run_agent_turn_executes_requested_tool_with_chat_completions(monkeypatch):
    tool_call = make_tool_call(
        "add_note",
        json.dumps({"content": "Review simple agent"}),
    )
    first_completion = make_completion(tool_calls=[tool_call])
    final_completion = make_completion(content="Saved it.")
    client = FakeChatClient([first_completion, final_completion])
    messages = []
    tool_calls = []
    events = []

    def fake_run_tool(name, arguments):
        tool_calls.append((name, arguments))
        return "Note saved."

    monkeypatch.setattr(agent, "run_tool", fake_run_tool)

    answer = agent.run_agent_turn(
        client,
        messages,
        "Remember: Review simple agent",
        model="test-model",
        on_tool_event=events.append,
    )

    assert answer == "Saved it."
    assert tool_calls == [("add_note", {"content": "Review simple agent"})]
    assert len(client.chat.completions.calls) == 2
    assert client.chat.completions.calls[0]["model"] == "test-model"
    assert client.chat.completions.calls[0]["tool_choice"] == "auto"
    assert client.chat.completions.calls[1]["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "call_123",
        "content": "Note saved.",
    }
    assert events == [
        {
            "type": "tool_call",
            "name": "add_note",
            "arguments": {"content": "Review simple agent"},
        },
        {
            "type": "tool_result",
            "name": "add_note",
            "output": "Note saved.",
            "is_error": False,
        },
    ]
    assert messages == [
        {"role": "user", "content": "Remember: Review simple agent"},
        {"role": "assistant", "content": "Saved it."},
    ]


def test_run_agent_turn_emits_structured_trace_events(monkeypatch):
    completion = make_completion(content="Hello there.")
    client = FakeChatClient([completion])
    events = []

    answer = agent.run_agent_turn(
        client,
        [],
        "Hello",
        model="test-model",
        on_event=events.append,
    )

    assert answer == "Hello there."
    assert [event["type"] for event in events] == [
        "user_message",
        "model_response",
        "final_answer",
    ]
    assert events[0]["content"] == "Hello"
    assert events[1]["model"] == "test-model"
    assert events[2]["content"] == "Hello there."


def test_run_agent_turn_reports_malformed_tool_arguments(monkeypatch):
    tool_call = make_tool_call("add_note", "{")
    client = FakeChatClient(
        [
            make_completion(tool_calls=[tool_call]),
            make_completion(content="I could not save that note."),
        ]
    )
    events = []

    def fail_if_called(name, arguments):
        raise AssertionError("run_tool should not be called with malformed JSON")

    monkeypatch.setattr(agent, "run_tool", fail_if_called)

    answer = agent.run_agent_turn(
        client,
        [],
        "Remember this",
        model="test-model",
        on_event=events.append,
    )

    assert answer == "I could not save that note."
    assert [event["type"] for event in events] == [
        "user_message",
        "model_response",
        "tool_error",
        "tool_result",
        "model_response",
        "final_answer",
    ]
    assert events[2]["name"] == "add_note"
    assert "Expecting property name" in events[2]["message"]
    assert events[3]["is_error"] is True
    assert events[3]["output"].startswith("Tool error:")


def test_run_agent_turn_reports_unknown_tools(monkeypatch):
    tool_call = make_tool_call("missing_tool", "{}")
    client = FakeChatClient(
        [
            make_completion(tool_calls=[tool_call]),
            make_completion(content="I cannot use that tool."),
        ]
    )
    events = []

    def fake_run_tool(name, arguments):
        raise ValueError(f"Unknown tool: {name}")

    monkeypatch.setattr(agent, "run_tool", fake_run_tool)

    answer = agent.run_agent_turn(
        client,
        [],
        "Use the missing tool",
        model="test-model",
        on_event=events.append,
    )

    assert answer == "I cannot use that tool."
    assert [event["type"] for event in events] == [
        "user_message",
        "model_response",
        "tool_call",
        "tool_error",
        "tool_result",
        "model_response",
        "final_answer",
    ]
    assert events[2]["arguments"] == {}
    assert events[3]["message"] == "Unknown tool: missing_tool"
    assert events[4]["is_error"] is True


def test_run_agent_turn_stops_after_max_tool_rounds(monkeypatch):
    completions = [
        make_completion(
            tool_calls=[
                make_tool_call(
                    "add_note",
                    json.dumps({"content": f"Loop note {index}"}),
                    call_id=f"call_{index}",
                )
            ]
        )
        for index in range(agent.MAX_TOOL_ROUNDS)
    ]
    client = FakeChatClient(completions)
    events = []

    monkeypatch.setattr(agent, "run_tool", lambda name, arguments: "Note saved.")

    with pytest.raises(RuntimeError, match="maximum number of tool rounds"):
        agent.run_agent_turn(
            client,
            [],
            "Keep saving notes",
            model="test-model",
            on_event=events.append,
        )

    assert len(client.chat.completions.calls) == agent.MAX_TOOL_ROUNDS
    assert [event["type"] for event in events].count("tool_call") == agent.MAX_TOOL_ROUNDS
    assert [event["type"] for event in events].count("tool_result") == agent.MAX_TOOL_ROUNDS


def test_print_tool_event_prints_tool_errors_once(capsys):
    agent.print_tool_event(
        {"type": "tool_error", "name": "add_note", "message": "bad arguments"}
    )
    agent.print_tool_event(
        {
            "type": "tool_result",
            "name": "add_note",
            "output": "Tool error: bad arguments",
            "is_error": True,
        }
    )

    assert capsys.readouterr().out == "Tool error: bad arguments\n"


def test_load_dotenv_sets_missing_environment_values(monkeypatch):
    env_path = FIXTURES_PATH / "deepseek.env"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "existing-model")

    agent.load_dotenv(env_path)

    assert agent.default_model() == "existing-model"
    assert agent.os.environ["OPENAI_API_KEY"] == "deepseek-key"
    assert agent.os.environ["OPENAI_BASE_URL"] == "https://api.deepseek.com"
    assert agent.os.environ["OPENAI_MODEL"] == "existing-model"


def test_load_dotenv_ignores_blank_values(monkeypatch):
    env_path = FIXTURES_PATH / "blank.env"
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    agent.load_dotenv(env_path)

    assert "OPENAI_MODEL" not in agent.os.environ
    assert agent.default_model() == "gpt-5.4-mini"
