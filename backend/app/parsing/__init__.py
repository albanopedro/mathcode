"""Safe input pipeline: text -> normalized text -> tokens -> AST (ADR 0002).

Nothing here evaluates the input. ``build`` turns the AST into SymPy objects
through explicit constructors.
"""

from dataclasses import dataclass

from app.core.notices import Notice
from app.parsing.ast import Tree
from app.parsing.normalize import normalize
from app.parsing.parser import parse_tokens
from app.parsing.printer import to_text
from app.parsing.tokenizer import tokenize


@dataclass(frozen=True)
class ParseResult:
    source: str
    tree: Tree
    notices: tuple[Notice, ...]

    @property
    def canonical(self) -> str:
        return to_text(self.tree)


def parse(source: str) -> ParseResult:
    notices: list[Notice] = []
    tokens = tokenize(normalize(source), notices)
    tree = parse_tokens(tokens, notices)
    return ParseResult(source=source, tree=tree, notices=tuple(notices))
