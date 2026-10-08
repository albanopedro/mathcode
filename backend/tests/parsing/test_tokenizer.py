import pytest

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice, NoticeCode
from app.parsing.normalize import normalize
from app.parsing.tokenizer import TokenKind, tokenize


def kinds_and_texts(source: str) -> list[tuple[TokenKind, str]]:
    return [(t.kind, t.text) for t in tokenize(normalize(source), [])]


def test_tokenizes_an_expression() -> None:
    assert kinds_and_texts("2x + sin(3.5)") == [
        (TokenKind.NUMBER, "2"),
        (TokenKind.IDENT, "x"),
        (TokenKind.PLUS, "+"),
        (TokenKind.IDENT, "sin"),
        (TokenKind.LPAREN, "("),
        (TokenKind.NUMBER, "3.5"),
        (TokenKind.RPAREN, ")"),
        (TokenKind.EOF, ""),
    ]


def test_double_star_is_power() -> None:
    assert kinds_and_texts("2**3")[1] == (TokenKind.CARET, "**")


def test_semicolon_separates_arguments() -> None:
    assert kinds_and_texts("log(8; 2)")[3] == (TokenKind.COMMA, ";")


@pytest.mark.parametrize(("source", "value"), [(".5", "0.5"), ("3.25", "3.25"), ("12", "12")])
def test_numbers(source: str, value: str) -> None:
    assert kinds_and_texts(source)[0] == (TokenKind.NUMBER, value)


def test_decimal_comma_becomes_point_with_notice() -> None:
    notices: list[Notice] = []
    tokens = tokenize(normalize("3,5"), notices)
    assert (tokens[0].kind, tokens[0].text) == (TokenKind.NUMBER, "3.5")
    assert [n.code for n in notices] == [NoticeCode.DECIMAL_COMMA]


def test_comma_followed_by_space_is_a_separator() -> None:
    assert [k for k, _ in kinds_and_texts("1, 2")] == [
        TokenKind.NUMBER,
        TokenKind.COMMA,
        TokenKind.NUMBER,
        TokenKind.EOF,
    ]


@pytest.mark.parametrize("source", ["1,2,3", "1.5.2", "1.5,2"])
def test_rejects_ambiguous_numbers(source: str) -> None:
    with pytest.raises(MathError) as exc:
        tokenize(normalize(source), [])
    assert exc.value.code is ErrorCode.AMBIGUOUS_INPUT


@pytest.mark.parametrize("source", ["1e5", "2E3", "2e-3", "3e+2"])
def test_rejects_scientific_notation_as_ambiguous(source: str) -> None:
    with pytest.raises(MathError) as exc:
        tokenize(normalize(source), [])
    assert exc.value.code is ErrorCode.AMBIGUOUS_INPUT


def test_number_times_e_with_space_is_not_scientific_notation() -> None:
    assert [k for k, _ in kinds_and_texts("2e + 3")][:3] == [
        TokenKind.NUMBER,
        TokenKind.IDENT,
        TokenKind.PLUS,
    ]


def test_point_without_digits_is_an_error() -> None:
    with pytest.raises(MathError) as exc:
        tokenize(normalize("3. + 1"), [])
    assert exc.value.code is ErrorCode.PARSE_ERROR


@pytest.mark.parametrize(
    ("source", "char", "position"),
    [("2 % 3", "%", 2), ("x#", "#", 1), ("a_b", "_", 1), ("2 & 3", "&", 2), ("½", "½", 0)],
)
def test_rejects_unsupported_characters_pointing_at_the_original(
    source: str, char: str, position: int
) -> None:
    with pytest.raises(MathError) as exc:
        tokenize(normalize(source), [])
    assert exc.value.code is ErrorCode.PARSE_ERROR
    assert exc.value.position == position
    assert f"'{char}'" in exc.value.message
