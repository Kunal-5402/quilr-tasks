"""Redaction over a stream, with a bounded hold-back buffer.

A pattern can split across 2 chunks, so the redactor holds back the tail that
could still grow into a match. In normal prose it holds one partial word, never
the whole response. The held tail stays raw, so a match is only redacted once
it is complete.
"""

from gateways.llm_stream_guard.patterns import (
    MAX_MATCH_LENGTH,
    PII,
    SEPARATORS,
    redact,
)

MAX_HOLD = MAX_MATCH_LENGTH


class StreamRedactor:
    def __init__(self, max_hold: int = MAX_HOLD) -> None:
        self._buffer = ""
        self._max_hold = max_hold

    @property
    def held(self) -> int:
        return len(self._buffer)

    def feed(self, text: str) -> str:
        """Return the text that is safe to send now."""
        self._buffer += text
        cut = self._cut_point(self._buffer)
        emitted, self._buffer = self._buffer[:cut], self._buffer[cut:]
        return redact(emitted)

    def flush(self) -> str:
        """Return the held text at the end of the stream."""
        remainder, self._buffer = self._buffer, ""
        return redact(remainder)

    def _cut_point(self, buffer: str) -> int:
        """The index up to which the text can no longer change."""
        floor = max(0, len(buffer) - self._max_hold)

        # No pattern contains a separator, so a match cannot cross one.
        for index in range(len(buffer) - 1, floor - 1, -1):
            if buffer[index] in SEPARATORS:
                return index + 1

        # A long run without a separator. Never cut through a match in progress.
        for match in PII.finditer(buffer):
            if match.start() < floor < match.end():
                return match.start()
        return floor
