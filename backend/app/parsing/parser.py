"""Pratt parser: tokens -> AST. See the grammar table in ADR 0002."""

from dataclasses import replace

from app.core.errors import ErrorCode, MathError
from app.core.limits import MAX_NESTING
from app.core.notices import Notice, NoticeCode
from app.parsing.ast import (
    Binary,
    Call,
    Constant,
    Degrees,
    Equation,
    Negate,
    Node,
    Number,
    Tree,
    Variable,
)
from app.parsing.tokenizer import Token, TokenKind
from app.parsing.vocabulary import ALIASES, CONSTANTS, FUNCTIONS, RESERVED

_INFIX = {
    TokenKind.PLUS: ("+", 10),
    TokenKind.MINUS: ("-", 10),
    TokenKind.STAR: ("*", 20),
    TokenKind.SLASH: ("/", 20),
    TokenKind.CARET: ("^", 40),
}
_IMPLICIT_BP = 20  # "2x" binds like "2*x"
_PREFIX_BP = 35  # unary minus: tighter than * and /, looser than ^ (-x^2 = -(x^2))
_SQRT_BP = 45  # √ takes the next atom only: √2x = √2·x
_DEGREE_BP = 50
_STARTS_IMPLICIT_FACTOR = {TokenKind.IDENT, TokenKind.LPAREN, TokenKind.SQRT}


def parse_tokens(tokens: list[Token], notices: list[Notice]) -> Tree:
    return _Parser(tokens, notices).parse()


class _Parser:
    def __init__(self, tokens: list[Token], notices: list[Notice]) -> None:
        self._tokens = tokens
        self._index = 0
        self._depth = 0
        self._notices = notices

    def parse(self) -> Tree:
        left = self._expression(0)
        if self._peek().kind is not TokenKind.EQUALS:
            self._expect_end()
            return left
        equals = self._advance()
        right = self._expression(0)
        if self._peek().kind is TokenKind.EQUALS:
            raise MathError(
                ErrorCode.PARSE_ERROR, "Use um único '=' por equação.", self._peek().position
            )
        self._expect_end()
        return Equation(left, right, equals.position)

    # -- Pratt core ---------------------------------------------------------

    def _expression(self, rbp: int) -> Node:
        self._depth += 1
        try:
            if self._depth > MAX_NESTING:
                raise MathError(
                    ErrorCode.LIMIT_EXCEEDED,
                    f"A expressão tem mais de {MAX_NESTING} níveis de aninhamento.",
                    self._peek().position,
                )
            left = self._nud(self._advance())
            while self._lbp(self._peek()) > rbp:
                left = self._led(self._peek(), left)
            return left
        finally:
            self._depth -= 1

    def _lbp(self, token: Token) -> int:
        if token.kind in _INFIX:
            return _INFIX[token.kind][1]
        if token.kind is TokenKind.DEGREE:
            return _DEGREE_BP
        if token.kind in _STARTS_IMPLICIT_FACTOR:
            return _IMPLICIT_BP
        if token.kind is TokenKind.NUMBER:
            raise MathError(
                ErrorCode.PARSE_ERROR,
                "Um número logo depois de outro termo é ambíguo. "
                "Use * para multiplicar ou ^ para potência (ex.: x*2 ou x^2).",
                token.position,
            )
        return 0

    def _nud(self, token: Token) -> Node:
        match token.kind:
            case TokenKind.NUMBER:
                return Number(token.text, token.position)
            case TokenKind.IDENT:
                return self._identifier(token)
            case TokenKind.MINUS:
                return Negate(self._expression(_PREFIX_BP), token.position)
            case TokenKind.PLUS:
                return self._expression(_PREFIX_BP)
            case TokenKind.LPAREN:
                inner = self._expression(0)
                self._expect_close(token)
                return replace(inner, grouped=True) if isinstance(inner, Binary) else inner
            case TokenKind.SQRT:
                return Call("sqrt", (self._expression(_SQRT_BP),), token.position)
            case TokenKind.EOF:
                raise MathError(
                    ErrorCode.PARSE_ERROR, "A expressão está incompleta.", token.position
                )
            case TokenKind.RPAREN:
                raise MathError(
                    ErrorCode.PARSE_ERROR, "Falta uma expressão antes de ')'.", token.position
                )
            case TokenKind.EQUALS:
                raise MathError(
                    ErrorCode.PARSE_ERROR, "Falta uma expressão antes do '='.", token.position
                )
            case TokenKind.COMMA:
                raise MathError(ErrorCode.PARSE_ERROR, "Vírgula fora de lugar.", token.position)
            case TokenKind.DEGREE:
                raise MathError(
                    ErrorCode.PARSE_ERROR,
                    "O símbolo ° precisa vir depois de um número.",
                    token.position,
                )
            case _:
                raise MathError(
                    ErrorCode.PARSE_ERROR,
                    f"Falta um termo antes de '{token.text}'.",
                    token.position,
                )

    def _led(self, token: Token, left: Node) -> Node:
        if token.kind in _INFIX:
            self._advance()
            op, bp = _INFIX[token.kind]
            right = self._expression(bp - 1 if op == "^" else bp)  # ^ is right-associative
            return Binary(op, left, right, token.position)
        if token.kind is TokenKind.DEGREE:
            self._advance()
            return Degrees(left, token.position)

        # Implicit multiplication: nothing to consume, the next factor starts here.
        if isinstance(left, Variable) and token.kind is TokenKind.LPAREN:
            self._notices.append(
                Notice(
                    NoticeCode.AMBIGUOUS_IMPLICIT_MULTIPLICATION,
                    f"'{left.name}(...)' foi lido como {left.name}·(...), uma multiplicação. "
                    "Notação de função, como f(x), ainda não é suportada.",
                )
            )
        right = self._expression(_IMPLICIT_BP)
        if isinstance(left, Binary) and left.op == "/" and not left.grouped:
            self._notices.append(
                Notice(
                    NoticeCode.AMBIGUOUS_IMPLICIT_MULTIPLICATION,
                    "Uma divisão seguida de multiplicação sem '*' (como 1/2x) foi lida como "
                    "(1/2)·x. Para 1/(2x), use parênteses.",
                )
            )
        return Binary("*", left, right, token.position, implicit=True)

    # -- pieces ---------------------------------------------------------------

    def _identifier(self, token: Token) -> Node:
        name = ALIASES.get(token.text, token.text)
        if name in FUNCTIONS:
            return self._call(token, name)
        if name in CONSTANTS:
            return Constant(name, token.position)
        if name in RESERVED:
            raise MathError(ErrorCode.UNSUPPORTED_FEATURE, RESERVED[name], token.position)
        if len(name) == 1:
            return Variable(name, token.position)
        if self._peek().kind is TokenKind.LPAREN:
            raise MathError(
                ErrorCode.UNKNOWN_FUNCTION, f"Função desconhecida: '{token.text}'.", token.position
            )
        hint = f" Para multiplicar, escreva {'*'.join(token.text)}." if len(token.text) <= 3 else ""
        raise MathError(
            ErrorCode.UNKNOWN_SYMBOL,
            f"Símbolo desconhecido: '{token.text}'. Variáveis têm uma letra só.{hint}",
            token.position,
        )

    def _call(self, name_token: Token, name: str) -> Node:
        opening = self._peek()
        if opening.kind is not TokenKind.LPAREN:
            raise MathError(
                ErrorCode.PARSE_ERROR,
                f"A função '{name_token.text}' precisa de parênteses, como em {name}(x).",
                name_token.position,
            )
        self._advance()
        args = [self._expression(0)]
        while self._peek().kind is TokenKind.COMMA:
            self._advance()
            args.append(self._expression(0))
        self._expect_close(opening)

        minimum, maximum = FUNCTIONS[name]
        if not minimum <= len(args) <= maximum:
            expected = str(minimum) if minimum == maximum else f"{minimum} ou {maximum}"
            raise MathError(
                ErrorCode.PARSE_ERROR,
                f"A função '{name}' recebe {expected} argumento(s), mas recebeu {len(args)}.",
                name_token.position,
            )
        return Call(name, tuple(args), name_token.position)

    # -- token helpers ----------------------------------------------------------

    def _peek(self) -> Token:
        return self._tokens[self._index]

    def _advance(self) -> Token:
        token = self._tokens[self._index]
        if token.kind is not TokenKind.EOF:
            self._index += 1
        return token

    def _expect_close(self, opening: Token) -> None:
        if self._peek().kind is not TokenKind.RPAREN:
            raise MathError(
                ErrorCode.PARSE_ERROR, "Parêntese aberto e não fechado.", opening.position
            )
        self._advance()

    def _expect_end(self) -> None:
        token = self._peek()
        if token.kind is TokenKind.EOF:
            return
        if token.kind is TokenKind.RPAREN:
            message = "Parêntese ')' sem o '(' correspondente."
        elif token.kind is TokenKind.COMMA:
            message = "Vírgula fora de uma função. Para número decimal, escreva sem espaço: 3,5."
        else:
            message = f"Trecho inesperado: '{token.text}'."
        raise MathError(ErrorCode.PARSE_ERROR, message, token.position)
