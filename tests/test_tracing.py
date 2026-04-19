import json
from pathlib import Path
from uuid import uuid4

from tracing import JsonlTracer


PROJECT_TMP = Path(__file__).resolve().parents[1] / "test_runs"


def temporary_trace_path():
    PROJECT_TMP.mkdir(exist_ok=True)
    return PROJECT_TMP / f"{uuid4().hex}.jsonl"


def test_jsonl_tracer_writes_structured_events():
    trace_path = temporary_trace_path()
    tracer = JsonlTracer(trace_path, run_id="run_123")

    tracer.record({"type": "tool_call", "name": "add_note"})

    event = json.loads(trace_path.read_text(encoding="utf-8"))
    assert event["run_id"] == "run_123"
    assert event["type"] == "tool_call"
    assert event["name"] == "add_note"
    assert event["timestamp"]
