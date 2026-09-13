"""Minimal Server-Sent Events parser and writer.

A frame can split across 2 HTTP chunks, so the parser keeps one partial frame.
"""

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SseEvent:
    event: str
    data: str

    @property
    def json(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.data)
        except ValueError:
            return None


class SseParser:
    def __init__(self) -> None:
        self._partial = ""

    def feed(self, chunk: str) -> list[SseEvent]:
        self._partial += chunk
        frames = self._partial.split("\n\n")
        self._partial = frames.pop()  # the last piece may be incomplete
        return [event for frame in frames if (event := _parse_frame(frame)) is not None]


def _parse_frame(frame: str) -> SseEvent | None:
    event, data_lines = "message", []
    for line in frame.splitlines():
        if line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
    return SseEvent(event, "\n".join(data_lines)) if data_lines else None


def build_event(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()
