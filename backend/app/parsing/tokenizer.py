from dataclasses import dataclass
from enum import StrEnum

from app.core.errors import ErrorCode, MathError
from app.core.notices import Notice, NoticeCode
from app.parsing.normalize import NormalizedText

DIGITS = frozenset("0123456789")
_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")


class TokenKind(StrEnum):
    NUMBER = "NUMBER"
    IDENT = "IDENT"
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    CARET = "^"
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    COMMA = ","
    EQUALS = "="
    SQRT = "√"
    DEGREE = "°"
    EOF = "EOF"


_SINGLE_CHAR = {
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.STAR,
    "/": TokenKind.SLASH,
    "^": TokenKind.CARET,
    "(": TokenKind.LPAREN,
    ")": TokenKind.RPAREN,
    "[": TokenKind.LBRACKET,
    "]": TokenKind.RBRACKET,
    ",": TokenKind.COMMA,
    ";": TokenKind.COMMA,
    "=": TokenKind.EQUALS,
    "√": TokenKind.SQRT,
    "°": TokenKind.DEGREE,
}


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str
    position: int  # index in the user's original input


def tokenize(norm: NormalizedText, notices: list[Notice]) -> list[Token]:
    text = norm.text
    tokens: list[Token] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == " ":
            i += 1
        elif ch in DIGITS or (ch == "." and _is_digit_at(text, i + 1)):
            token, i = _read_number(norm, i, notices)
            tokens.append(token)
        elif ch in _LETTERS:
            start = i
            while i < len(text) and text[i] in _LETTERS:
                i += 1
            tokens.append(Token(TokenKind.IDENT, text[start:i], norm.origin(start)))
        elif text.startswith("**", i):
            tokens.append(Token(TokenKind.CARET, "**", norm.origin(i)))
            i += 2
        elif ch in _SINGLE_CHAR:
            tokens.append(Token(_SINGLE_CHAR[ch], ch, norm.origin(i)))
            i += 1
        else:
            position = norm.origin(i)
            raise MathError(
                ErrorCode.PARSE_ERROR,
                f"Caractere não suportado: '{norm.source[position]}'.",
                position,
            )
    tokens.append(Token(TokenKind.EOF, "", len(norm.source)))
    return tokens


def _is_digit_at(text: str, i: int) -> bool:
    return i < len(text) and text[i] in DIGITS


def _decimal_separator_at(text: str, i: int) -> bool:
    return i < len(text) and text[i] in ".," and _is_digit_at(text, i + 1)


def _read_number(norm: NormalizedText, start: int, notices: list[Notice]) -> tuple[Token, int]:
    text = norm.text
    i = start
    while _is_digit_at(text, i):
        i += 1
    integer = text[start:i] or "0"
    fraction = ""

    if _decimal_separator_at(text, i):
        separator = text[i]
        i += 1
        fraction_start = i
        while _is_digit_at(text, i):
            i += 1
        fraction = text[fraction_start:i]
        if _decimal_separator_at(text, i):
            end = i
            while end < len(text) and (text[end] in DIGITS or text[end] in ".,"):
                end += 1
            raise MathError(
                ErrorCode.AMBIGUOUS_INPUT,
                f"O número '{text[start:end]}' é ambíguo: use um único separador decimal. "
                "Para separar valores, use '; '.",
                norm.origin(start),
            )
        if separator == ",":
            notices.append(
                Notice(
                    NoticeCode.DECIMAL_COMMA,
                    f"'{integer},{fraction}' foi lido como o número decimal {integer}.{fraction}.",
                )
            )
    elif i < len(text) and text[i] == ".":
        raise MathError(
            ErrorCode.PARSE_ERROR, "Ponto decimal sem dígitos depois dele.", norm.origin(i)
        )

    # "1e5" could be scientific notation or 1·e·5; refuse to guess.
    if (
        i < len(text)
        and text[i] in "eE"
        and (
            _is_digit_at(text, i + 1)
            or (i + 1 < len(text) and text[i + 1] in "+-" and _is_digit_at(text, i + 2))
        )
    ):
        raise MathError(
            ErrorCode.AMBIGUOUS_INPUT,
            "Notação como '1e5' é ambígua. Para potência de dez, escreva 1*10^5; "
            "para multiplicar pelo número e, escreva 1*e*5.",
            norm.origin(i),
        )

    value = f"{integer}.{fraction}" if fraction else integer
    return Token(TokenKind.NUMBER, value, norm.origin(start)), i
