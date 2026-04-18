import json
from types import SimpleNamespace

import agent


class FakeResponses:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.responses = FakeResponses(responses)


def test_run_agent_turn_executes_requested_tool(monkeypatch):
    first_response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                name="add_note",
                arguments=json.dumps({"content": "Review simple agent"}),
                call_id="call_123",
            )
        ],
        output_text="",
    )
    final_response = SimpleNamespace(output=[], output_text="Saved it.")
    client = FakeClient([first_response, final_response])
    messages = []
    tool_calls = []

    def fake_run_tool(name, arguments):
        tool_calls.append((name, arguments))
        return "Note saved."

    monkeypatch.setattr(agent, "run_tool", fake_run_tool)

    answer = agent.run_agent_turn(client, messages, "Remember: Review simple agent", model="test-model")

    assert answer == "Saved it."
    assert tool_calls == [("add_note", {"content": "Review simple agent"})]
    assert len(client.responses.calls) == 2
    assert client.responses.calls[1]["input"][-1] == {
        "type": "function_call_output",
        "call_id": "call_123",
        "output": "Note saved.",
    }
