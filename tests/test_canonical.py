import datetime
import decimal
from decimal import Decimal

import pytest

from entelechy.foundation.canonical import (
    MAX_DECIMAL_TEXT,
    CanonicalError,
    canonical_bytes,
    decimal_text,
    digest,
    digest_of,
    parse,
    verify,
)


def test_keys_are_sorted_and_whitespace_free() -> None:
    assert canonical_bytes({"b": 1, "a": [True, None, "x"]}) == b'{"a":[true,null,"x"],"b":1}'


def test_unicode_is_written_as_utf8_not_escapes() -> None:
    assert canonical_bytes("Ω") == '"Ω"'.encode()


def test_tuples_encode_as_arrays() -> None:
    assert canonical_bytes(("a", 1)) == b'["a",1]'


def test_floats_are_forbidden() -> None:
    value: object = {"confidence": 0.8}
    with pytest.raises(CanonicalError, match="floats"):
        canonical_bytes(value)  # type: ignore[arg-type]


def test_dates_are_forbidden_seq3() -> None:
    value: object = [datetime.date(2026, 9, 26)]
    with pytest.raises(CanonicalError, match="SEQ-3"):
        canonical_bytes(value)  # type: ignore[arg-type]


def test_non_string_keys_are_rejected() -> None:
    value: object = {1: "x"}
    with pytest.raises(CanonicalError, match="keys"):
        canonical_bytes(value)  # type: ignore[arg-type]


def test_lone_surrogates_are_rejected() -> None:
    with pytest.raises(CanonicalError, match="Unicode"):
        canonical_bytes("\ud800")


def test_decimal_text_is_normalized() -> None:
    assert decimal_text(Decimal("0.80")) == "0.8"
    assert decimal_text(Decimal("100")) == "100"
    assert decimal_text(Decimal("-0")) == "0"


def test_non_finite_decimals_have_no_text() -> None:
    with pytest.raises(CanonicalError, match="non-finite"):
        decimal_text(Decimal("NaN"))


def test_decimal_text_is_exact_and_ignores_the_ambient_context() -> None:
    nines = "0." + "9" * 29
    with decimal.localcontext() as context:
        context.prec = 6
        assert decimal_text(Decimal("0.12345678")) == "0.12345678"
        assert decimal_text(Decimal(nines)) == nines
    tiny_difference = Decimal("0.5000000000000000000000000000001")
    assert decimal_text(tiny_difference) != decimal_text(Decimal("0.5"))


def test_decimal_text_refuses_unbounded_lengths() -> None:
    with pytest.raises(CanonicalError, match="too long"):
        decimal_text(Decimal("1E-1000030"))


def test_the_decimal_length_bound_counts_the_text_exactly() -> None:
    longest = "0." + "1" * (MAX_DECIMAL_TEXT - 2)
    assert decimal_text(Decimal(longest)) == longest
    with pytest.raises(CanonicalError, match="too long"):
        decimal_text(Decimal(longest + "1"))
    # A Decimal made from a float is long but well within the bound.
    assert decimal_text(Decimal(0.7)).startswith("0.69999")


def test_integers_too_large_to_encode_are_canonical_errors() -> None:
    with pytest.raises(CanonicalError):
        canonical_bytes(10**5000)
    with pytest.raises(CanonicalError):
        parse(b"1" * 5000)


def test_decimals_need_a_typed_schema() -> None:
    # Otherwise Decimal("0.8") and the string "0.8" would share one encoding.
    value: object = [Decimal("0.8")]
    with pytest.raises(CanonicalError, match="typed schema"):
        canonical_bytes(value)  # type: ignore[arg-type]


def test_digest_names_its_algorithm() -> None:
    value = digest(b"abc")
    assert value.startswith("sha256:")
    assert len(value) == len("sha256:") + 64
    assert verify(b"abc", value)
    assert not verify(b"abd", value)


def test_unknown_digest_algorithm_is_refused() -> None:
    with pytest.raises(CanonicalError, match="unsupported"):
        verify(b"abc", "md5:900150983cd24fb0d6963f7d28e17f72")


def test_digest_of_hashes_the_canonical_bytes() -> None:
    assert digest_of({"a": 1}) == digest(b'{"a":1}')


def test_parse_round_trips_canonical_bytes() -> None:
    assert parse(canonical_bytes({"a": [1, "two", None]})) == {"a": [1, "two", None]}


def test_parse_refuses_non_canonical_bytes() -> None:
    with pytest.raises(CanonicalError, match="canonical form"):
        parse(b'{"b":1, "a":2}')


def test_parse_refuses_floats() -> None:
    with pytest.raises(CanonicalError, match="floats"):
        parse(b"[0.5]")


def test_parse_refuses_invalid_utf8() -> None:
    with pytest.raises(CanonicalError, match="not canonical JSON"):
        parse(b"\xff")
