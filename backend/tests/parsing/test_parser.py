import pytest

from app.core.errors import ErrorCode, MathError
from app.core.limits import MAX_NESTING, MAX_SYSTEM_EQUATIONS
from app.core.notices import NoticeCode
from app.parsing import parse
from app.parsing.ast import (
    Binary,
    Call,
    Equation,
    ExpressionList,
    Negate,
    Number,
    System,
    Variable,
    variables,
)


def canonical(source: str) -> str:
    return parse(source).canonical


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # precedence and associativity
        ("1 + 2*3", "1 + 2*3"),
        ("(1 + 2)*3", "(1 + 2)*3"),
        ("2^3^2", "2^3^2"),
        ("(2^3)^2", "(2^3)^2"),
        ("-x^2", "-x^2"),
        ("(-x)^2", "(-x)^2"),
        ("2^-3", "2^(-3)"),
        ("2 - -3", "2 - -3"),
        ("+5", "5"),
        ("10 - (3 - 2)", "10 - (3 - 2)"),
        ("8/(4/2)", "8/(4/2)"),
        # implicit multiplication
        ("2x", "2*x"),
        ("2(x + 1)", "2*(x + 1)"),
        ("(x + 1)(x - 1)", "(x + 1)*(x - 1)"),
        ("2pi", "2*pi"),
        ("x sin(x)", "x*sin(x)"),
        ("2x^2", "2*x^2"),
        ("2^3x", "2^3*x"),
        # functions, aliases, prefix root and degrees
        ("sen(30°)", "sin(30°)"),
        ("tg(x) + arcsen(1)", "tan(x) + asin(1)"),
        ("raiz(9)", "sqrt(9)"),
        ("√2x", "sqrt(2)*x"),
        ("√(x + 1)", "sqrt(x + 1)"),
        ("log(8; 2)", "log(8, 2)"),
        ("log(8, 2)", "log(8, 2)"),
        # input conveniences
        ("x² + 3x + 5", "x^2 + 3*x + 5"),
        ("2**10", "2^10"),
        ("2x + 5 = 17", "2*x + 5 = 17"),
    ],
)
def test_canonical_form(source: str, expected: str) -> None:
    assert canonical(source) == expected


def test_canonical_form_parses_back_to_the_same_tree() -> None:
    for source in ["1/2x", "-(x + 1)^2", "2^3^2 - 4/5*6", "sin(30°)*√3", "x - (y - z)"]:
        first = parse(source)
        assert parse(first.canonical).canonical == first.canonical


def test_tree_shape() -> None:
    tree = parse("2x + 1").tree
    assert isinstance(tree, Binary) and tree.op == "+"
    assert isinstance(tree.left, Binary) and tree.left.implicit
    assert tree.left.left == Number("2", 0)
    assert tree.left.right == Variable("x", 1)


def test_unary_minus_binds_looser_than_power() -> None:
    tree = parse("-2^2").tree
    assert isinstance(tree, Negate)
    assert isinstance(tree.operand, Binary) and tree.operand.op == "^"


def test_equation_and_variables() -> None:
    tree = parse("2x + y = 3").tree
    assert isinstance(tree, Equation)
    assert variables(tree) == {"x", "y"}


def test_sqrt_symbol_becomes_a_call() -> None:
    tree = parse("√9").tree
    assert isinstance(tree, Call) and tree.name == "sqrt"


def test_division_followed_by_implicit_product_warns() -> None:
    parsed = parse("1/2x")
    assert parsed.canonical == "(1/2)*x"
    assert [n.code for n in parsed.notices] == [NoticeCode.AMBIGUOUS_IMPLICIT_MULTIPLICATION]


def test_grouped_division_does_not_warn() -> None:
    assert parse("(1/2)x").notices == ()
    assert parse("1/(2x)").notices == ()


@pytest.mark.parametrize(
    ("source", "code", "position"),
    [
        ("2 +", ErrorCode.PARSE_ERROR, 3),
        ("(2 + 3", ErrorCode.PARSE_ERROR, 0),
        ("2 + 3)", ErrorCode.PARSE_ERROR, 5),
        ("()", ErrorCode.PARSE_ERROR, 1),
        ("* 2", ErrorCode.PARSE_ERROR, 0),
        ("= 2", ErrorCode.PARSE_ERROR, 0),
        ("x = 1 = 2", ErrorCode.PARSE_ERROR, 6),
        ("x == 2", ErrorCode.PARSE_ERROR, 3),
        ("x2", ErrorCode.PARSE_ERROR, 1),
        ("2 3", ErrorCode.PARSE_ERROR, 2),
        ("(x)2", ErrorCode.PARSE_ERROR, 3),
        ("sin x", ErrorCode.PARSE_ERROR, 0),
        ("sin()", ErrorCode.PARSE_ERROR, 4),
        ("sqrt(4, 2)", ErrorCode.PARSE_ERROR, 0),
        ("log(1; 2; 3)", ErrorCode.PARSE_ERROR, 0),
        ("1, 2", ErrorCode.PARSE_ERROR, 1),
        ("°", ErrorCode.PARSE_ERROR, 0),
        ("xy", ErrorCode.UNKNOWN_SYMBOL, 0),
        ("abc + 1", ErrorCode.UNKNOWN_SYMBOL, 0),
        ("foo(2)", ErrorCode.UNKNOWN_FUNCTION, 0),
        ("i + 1", ErrorCode.UNSUPPORTED_FEATURE, 0),
    ],
)
def test_errors(source: str, code: ErrorCode, position: int) -> None:
    with pytest.raises(MathError) as exc:
        parse(source)
    assert exc.value.code is code
    assert exc.value.position == position


def test_unknown_short_name_suggests_multiplication() -> None:
    with pytest.raises(MathError) as exc:
        parse("xy")
    assert "x*y" in exc.value.message


def test_nesting_limit() -> None:
    parse("(" * (MAX_NESTING - 1) + "x" + ")" * (MAX_NESTING - 1))
    with pytest.raises(MathError) as exc:
        parse("(" * (MAX_NESTING + 1) + "x" + ")" * (MAX_NESTING + 1))
    assert exc.value.code is ErrorCode.LIMIT_EXCEEDED


@pytest.mark.parametrize("source", ["-" * 150 + "1", "2^" * 120 + "2"])
def test_nesting_limit_covers_signs_and_powers(source: str) -> None:
    with pytest.raises(MathError) as exc:
        parse(source)
    assert exc.value.code is ErrorCode.LIMIT_EXCEEDED


def test_long_flat_sum_is_accepted() -> None:
    parse("+".join(["1"] * 240))


def test_system_of_equations() -> None:
    tree = parse("x + y = 3; x - y = 1").tree
    assert isinstance(tree, System)
    assert len(tree.equations) == 2
    assert parse("x + y = 3, x - y = 1").canonical == "x + y = 3; x - y = 1"


def test_system_parts_must_be_equations() -> None:
    with pytest.raises(MathError) as exc:
        parse("x + y = 3; x - y")
    assert exc.value.code is ErrorCode.PARSE_ERROR
    assert "equação" in exc.value.message


def test_system_size_limit() -> None:
    parse("; ".join(f"x = {n}" for n in range(MAX_SYSTEM_EQUATIONS)))
    with pytest.raises(MathError) as exc:
        parse("; ".join(f"x = {n}" for n in range(MAX_SYSTEM_EQUATIONS + 1)))
    assert exc.value.code is ErrorCode.LIMIT_EXCEEDED


def test_list_of_expressions() -> None:
    tree = parse("x^2; 2x + 1").tree
    assert isinstance(tree, ExpressionList)
    assert len(tree.expressions) == 2
    assert parse("x^2, 2x + 1").canonical == "x^2; 2*x + 1"


def test_list_of_numbers_is_still_a_comma_mistake() -> None:
    with pytest.raises(MathError) as exc:
        parse("1, 2")
    assert "decimal" in exc.value.message
