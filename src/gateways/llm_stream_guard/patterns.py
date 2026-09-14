"""PII patterns.

Every part is bounded, and no part nests a quantifier, so the engine cannot
backtrack out of control on a long stream.
"""

import re

EMAIL = r"[\w.+-]{1,64}@[\w-]{1,63}\.[A-Za-z]{2,24}"
SSN = r"\d{3}-\d{2}-\d{4}"
CARD = r"\d(?:[ -]?\d){12,18}"

PII = re.compile(rf"(?P<email>{EMAIL})|(?P<ssn>{SSN})|(?P<card>{CARD})")

REDACTED = "[REDACTED]"

# The longest text a pattern can match is an email at 64 + 1 + 63 + 1 + 24.
MAX_MATCH_LENGTH = 153

# A character that no pattern contains. Text before the last one is safe to emit.
SEPARATORS = frozenset(" \t\n\r,;:!?\"'()[]{}<>")


def is_luhn_valid(digits: str) -> bool:
    numbers = [int(c) for c in digits if c.isdigit()]
    total = 0
    for index, digit in enumerate(reversed(numbers)):
        if index % 2:
            digit *= 2
            digit -= 9 if digit > 9 else 0
        total += digit
    return total % 10 == 0


def redact(text: str) -> str:
    """Replace every complete match. A card number must pass the Luhn check."""

    def replace(match: re.Match[str]) -> str:
        if match.lastgroup == "card" and not is_luhn_valid(match.group()):
            return match.group()
        return REDACTED

    return PII.sub(replace, text)
