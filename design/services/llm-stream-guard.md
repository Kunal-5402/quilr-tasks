# LLM stream guard

Package: `gateways.llm_stream_guard`. Port 8003.
Covers T3-R1 to T3-R7. See ADR-007 and ADR-008.
PII means personally identifiable information.

## The core problem

A pattern can split across 2 chunks. The provider sends `"my mail is a@b."`
and then `"com now"`. A redactor that works on one chunk alone misses the
email. A redactor that waits for the end of the stream breaks the TTFT rule.

The answer is a hold-back buffer with a bounded size.

## `StreamRedactor`

```python
class StreamRedactor:
    def feed(self, text: str) -> str: ...   # returns the safe text to emit now
    def flush(self) -> str: ...             # returns the last held text, redacted
```

State: one string, `self._buf`. Nothing else.

### The `feed` algorithm

1. Append the new text to `self._buffer`.
2. Find the cut point. The cut point is the start of the tail that the redactor
   must hold.
3. Emit `redact(self._buffer[:cut])`. Keep `self._buffer = self._buffer[cut:]`.

The held tail stays raw, so a match is redacted only once it is complete.

### How to find the cut point

The redactor holds back the shortest tail that could still grow into a match.

1. Set `floor = max(0, len(buffer) - MAX_HOLD)`.
2. Walk back from the end to `floor`. Return `i + 1` for the last index `i`
   where `buffer[i]` is a separator. A separator is a character that no pattern
   contains: a space, a tab, a newline, a comma, a bracket, and similar.
3. If no separator is in that window, the run is long. Check every match in the
   buffer. If a match spans `floor`, return its start. Else return `floor`.

`MAX_HOLD` is 153, the longest text the email pattern can match: 64 + 1 + 63 +
1 + 24. Step 3 can push the buffer past `MAX_HOLD`, but never past
`2 * MAX_HOLD`.

### Why the buffer is bounded

Step 2 or step 3 always returns a cut. The buffer length is at most
`2 * MAX_HOLD` after each call to `feed`. The memory use does not grow with the
response length. This satisfies T3-R6.

### The TTFT effect

Normal prose holds spaces often. The redactor emits almost every word at once
and holds only the final partial word. The added latency is one word, not one
response. This satisfies T3-R7.

## Patterns

| Name | Pattern sketch | Note |
| --- | --- | --- |
| email | `[\w.+-]{1,64}@[\w-]{1,63}\.[A-Za-z]{2,24}` | Bounded on each part. No nested quantifier. |
| ssn | `\b\d{3}-\d{2}-\d{4}\b` | The United States social security number format. |
| credit card | `\b(?:\d[ -]?){13,19}\b` | Then apply the Luhn check to reduce false positives. |

Compile the patterns one time into a single alternation with named groups.
One pass over the buffer is then enough.

Every pattern is bounded. No pattern holds a nested quantifier. The regular
expression engine therefore cannot backtrack catastrophically.

The Luhn check runs only on a credit card candidate. A match that fails the
Luhn check stays in the text. The README states this behaviour.

## The SSE layer

`sse.py` holds 2 functions:

```python
def iter_events(chunk: str) -> Iterator[SseEvent]   # a stateful frame parser
def build_event(event: str, data: dict) -> bytes    # builds "event: ...\ndata: ...\n\n"
```

The parser keeps a small partial-frame buffer, because an SSE frame can also
split across 2 HTTP chunks. The parser emits a frame only on a blank line.

The proxy:

1. Opens the provider stream with `client.stream("POST", ...)`.
2. Reads with `aiter_bytes()`, not `aiter_lines()`, so no line buffering hides latency.
3. For each frame, takes the delta text field.
4. Calls `redactor.feed(delta)`.
5. If the result is not empty, builds a new frame and yields it at once.
6. At the `message_stop` frame, calls `redactor.flush()` and yields the last text.
7. Yields the terminal frame.

The response uses `StreamingResponse` with the media type
`text/event-stream` and the header `X-Accel-Buffering: no`.

## Test list

| Test | Requirement |
| --- | --- |
| An email inside one chunk is redacted. | T3-R4, T3-R5 |
| An email split at every possible offset is redacted. The test loops over each offset. | T3-R3, T3-R4 |
| An SSN split across 3 chunks is redacted. | T3-R4 |
| A valid credit card number is redacted. An invalid one is not. | T3-R4 |
| The buffer length never exceeds `MAX_HOLD` for prose with separators. | T3-R6 |
| The buffer length never exceeds `2 * MAX_HOLD` for a run with no separator. | T3-R6 |
| The first frame reaches the client before the provider ends the stream. | T3-R7 |
| `flush` redacts a pattern that ends the stream with no trailing separator. | T3-R4 |

## Benchmark

`scripts/bench_ttft.py` reports the TTFT with the guardrail on and off. The
README records both numbers. The target is an added TTFT under 5 ms.

## Run it

```
uv run python -m gateways.llm_stream_guard --provider   # the mock provider, port 8013
uv run python -m gateways.llm_stream_guard              # the gateway, port 8003
bash scripts/demo_stream_guard.sh                       # both, plus a live stream
```
