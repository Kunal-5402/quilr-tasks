import pytest

from gateways.llm_stream_guard.patterns import is_luhn_valid
from gateways.llm_stream_guard.redactor import MAX_HOLD, StreamRedactor

VISA = "4111111111111111"
BAD_CARD = "4111111111111112"


def run(chunks: list[str]) -> str:
    redactor = StreamRedactor()
    return "".join(redactor.feed(chunk) for chunk in chunks) + redactor.flush()


@pytest.mark.req("T3-R4", "T3-R5")
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mail me at ada@example.com now", "mail me at [REDACTED] now"),
        ("ssn 123-45-6789 ok", "ssn [REDACTED] ok"),
        (f"card {VISA} ok", "card [REDACTED] ok"),
        ("nothing to hide here", "nothing to hide here"),
        (f"invalid {BAD_CARD} stays", f"invalid {BAD_CARD} stays"),
    ],
)
def test_a_pattern_inside_one_chunk_is_redacted(text, expected):
    assert run([text]) == expected


@pytest.mark.req("T3-R3", "T3-R4")
@pytest.mark.parametrize(
    "text",
    [
        "contact ada@example.com today",
        "ssn is 123-45-6789.",
        f"pay with {VISA} please",
    ],
)
def test_a_pattern_split_at_any_offset_is_redacted(text):
    for offset in range(1, len(text)):
        assert run([text[:offset], text[offset:]]) == run([text]), f"split at {offset}"


@pytest.mark.req("T3-R4")
def test_a_pattern_split_across_many_chunks_is_redacted():
    assert run(list("ssn 123-45-6789 done")) == "ssn [REDACTED] done"


@pytest.mark.req("T3-R4")
def test_flush_redacts_a_pattern_that_ends_the_stream():
    assert run(["write to ada@example.com"]) == "write to [REDACTED]"


@pytest.mark.req("T3-R4")
def test_several_patterns_in_one_stream_are_all_redacted():
    text = f"a@b.co and 123-45-6789 and {VISA} end"
    assert run([text]) == "[REDACTED] and [REDACTED] and [REDACTED] end"


@pytest.mark.req("T3-R6")
def test_the_buffer_stays_bounded_over_a_long_stream():
    redactor = StreamRedactor()
    peak = 0
    for _ in range(5000):
        redactor.feed("lorem ipsum dolor sit amet ")
        peak = max(peak, redactor.held)
    assert peak <= MAX_HOLD


@pytest.mark.req("T3-R6")
def test_the_buffer_stays_bounded_without_any_separator():
    redactor = StreamRedactor()
    peak = 0
    for _ in range(2000):
        redactor.feed("abcdefghij")
        peak = max(peak, redactor.held)
    assert peak <= 2 * MAX_HOLD


@pytest.mark.req("T3-R7")
def test_normal_prose_holds_back_at_most_one_partial_word():
    redactor = StreamRedactor()
    emitted = redactor.feed("the quick brown fox jum")
    assert emitted == "the quick brown fox "
    assert redactor.held == len("jum")


@pytest.mark.req("T3-R4")
@pytest.mark.parametrize(("digits", "valid"), [(VISA, True), (BAD_CARD, False)])
def test_luhn_check(digits, valid):
    assert is_luhn_valid(digits) is valid
