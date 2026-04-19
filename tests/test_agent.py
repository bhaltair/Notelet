import json
from pathlib import Path
from types import SimpleNamespace

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


def test_run_agent_turn_executes_requested_tool_with_chat_completions(monkeypatch):
    tool_call = SimpleNamespace(
        id="call_123",
        function=SimpleNamespace(
            name="add_note",
            arguments=json.dumps({"content": "Review simple agent"}),
        ),
    )
    first_completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=[tool_call])
            )
        ]
    )
    final_completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="Saved it.", tool_calls=None)
            )
        ]
    )
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
        },
    ]
    assert messages == [
        {"role": "user", "content": "Remember: Review simple agent"},
        {"role": "assistant", "content": "Saved it."},
    ]


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
