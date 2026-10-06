import pytest

from app.core.errors import ErrorCode, MathError
from app.core.limits import MAX_INPUT_LENGTH
from app.parsing.normalize import normalize


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x²", "x^2"),
        ("x³ + y¹⁰", "x^3 + y^(10)"),
        ("x⁻¹", "x^(-1)"),
        ("2×3", "2*3"),
        ("2·3", "2*3"),
        ("6÷2", "6/2"),
        ("5−3", "5-3"),  # Unicode minus sign
        ("2π", "2pi"),
        ("30º", "30°"),  # ordinal indicator typed as degree
        ("\uff13\uff0b\uff14", "3+4"),  # full-width digits and plus (NFKC)
        ("2\tx", "2 x"),
    ],
)
def test_normalizes_characters(source: str, expected: str) -> None:
    assert normalize(source).text == expected


def test_keeps_sqrt_and_degree_symbols() -> None:
    assert normalize("√2 + 30°").text == "√2 + 30°"


def test_tracks_original_positions() -> None:
    norm = normalize("x² + π")
    # "x^2 + pi": "^" and "2" both come from "²" (index 1); "pi" comes from "π" (index 5).
    assert norm.text == "x^2 + pi"
    assert norm.origin(1) == 1
    assert norm.origin(2) == 1
    assert norm.origin(6) == 5
    assert norm.origin(7) == 5
    assert norm.origin(len(norm.text)) == len("x² + π")


@pytest.mark.parametrize("source", ["", "   ", "\n\t"])
def test_rejects_empty_input(source: str) -> None:
    with pytest.raises(MathError) as exc:
        normalize(source)
    assert exc.value.code is ErrorCode.EMPTY_INPUT


def test_rejects_input_over_the_limit() -> None:
    normalize("1" * MAX_INPUT_LENGTH)  # exactly at the limit is fine
    with pytest.raises(MathError) as exc:
        normalize("1" * (MAX_INPUT_LENGTH + 1))
    assert exc.value.code is ErrorCode.INPUT_TOO_LONG
