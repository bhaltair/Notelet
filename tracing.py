from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


TRACE_DIR = Path(__file__).with_name("traces")


class JsonlTracer:
    def __init__(self, trace_path: Path | None = None, run_id: str | None = None) -> None:
        self.run_id = run_id or uuid4().hex
        self.trace_path = trace_path or default_trace_path()

    def record(self, event: dict[str, object]) -> None:
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
            "run_id": self.run_id,
            **event,
        }
        with self.trace_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def default_trace_path() -> Path:
    date = datetime.now(timezone.utc).astimezone().date().isoformat()
    return TRACE_DIR / f"{date}.jsonl"
