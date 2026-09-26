"""Canonical bytes and versioned digests.

Every persistent structure has exactly one byte representation before it is
hashed (design §5.1). The canonical layer accepts only the plain JSON subset,
so distinct values always encode to distinct bytes. Typed schemas convert
their Decimal fields with decimal_text and decode them by field.

Floats have no canonical form because their formatting drifts. Dates and
times have none because ordering machinery is not a concept of time
(FOUNDATIONS SEQ-3).
"""

import datetime
import hashlib
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal

type Canonical = None | bool | int | str | Sequence[Canonical] | Mapping[str, Canonical]
type Json = None | bool | int | str | list[Json] | dict[str, Json]

DIGEST_ALGORITHM = "sha256"


class CanonicalError(ValueError):
    """A value has no canonical representation, or bytes are not canonical."""


def decimal_text(value: Decimal) -> str:
    """Normalized fixed-point text for typed schemas: Decimal("0.80") -> "0.8"."""
    if not value.is_finite():
        raise CanonicalError(f"non-finite decimal {value}")
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")


def _prepare(value: object) -> Json:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        raise CanonicalError("a Decimal needs a typed schema; encode it with decimal_text")
    if isinstance(value, float):
        raise CanonicalError("floats are forbidden in canonical content; use Decimal")
    if isinstance(value, (datetime.date, datetime.time, datetime.timedelta)):
        raise CanonicalError("dates and times are not canonical content (SEQ-3)")
    if isinstance(value, (list, tuple)):
        return [_prepare(item) for item in value]
    if isinstance(value, Mapping):
        prepared: dict[str, Json] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalError(f"object keys must be strings, not {type(key).__name__}")
            prepared[key] = _prepare(item)
        return prepared
    raise CanonicalError(f"{type(value).__name__} has no canonical form")


def canonical_bytes(value: Canonical) -> bytes:
    """The one byte representation of `value`: sorted keys, no whitespace, UTF-8."""
    text = json.dumps(
        _prepare(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise CanonicalError(f"text is not valid Unicode: {error.reason}") from error


def digest(data: bytes) -> str:
    """A digest that names its algorithm, so the algorithm can be replaced later."""
    return f"{DIGEST_ALGORITHM}:{hashlib.sha256(data).hexdigest()}"


def digest_of(value: Canonical) -> str:
    return digest(canonical_bytes(value))


def verify(data: bytes, expected: str) -> bool:
    algorithm, separator, _ = expected.partition(":")
    if separator != ":" or algorithm != DIGEST_ALGORITHM:
        raise CanonicalError(f"unsupported digest {expected!r}")
    return digest(data) == expected


def _reject_float(text: str) -> object:
    raise CanonicalError(f"floats are forbidden in canonical content: {text}")


def _reject_constant(text: str) -> object:
    raise CanonicalError(f"non-finite number {text} in canonical content")


def parse(data: bytes) -> Json:
    """Decode canonical bytes, refusing anything that is not already canonical."""
    try:
        text = data.decode("utf-8")
        value: Json = json.loads(
            text, parse_float=_reject_float, parse_constant=_reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CanonicalError(f"not canonical JSON: {error}") from error
    if canonical_bytes(value) != data:
        raise CanonicalError("bytes are not in canonical form")
    return value
