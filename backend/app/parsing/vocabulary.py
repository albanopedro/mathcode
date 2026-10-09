"""The closed list of names the parser accepts. Anything else is rejected."""

# Canonical function name -> (minimum, maximum) number of arguments.
FUNCTIONS: dict[str, tuple[int, int]] = {
    "sqrt": (1, 1),
    "abs": (1, 1),
    "sin": (1, 1),
    "cos": (1, 1),
    "tan": (1, 1),
    "sec": (1, 1),
    "csc": (1, 1),
    "cot": (1, 1),
    "asin": (1, 1),
    "acos": (1, 1),
    "atan": (1, 1),
    "exp": (1, 1),
    "ln": (1, 1),
    "log": (1, 2),
}

# Portuguese and alternative spellings -> canonical name.
ALIASES: dict[str, str] = {
    "sen": "sin",
    "tg": "tan",
    "raiz": "sqrt",
    "arcsen": "asin",
    "arcsin": "asin",
    "arccos": "acos",
    "arctan": "atan",
    "arctg": "atan",
    "cossec": "csc",
    "cosec": "csc",
    "cotg": "cot",
    "cotan": "cot",
}

# Counting (ADR 0015): C(n, k) and A(n, k) are functions only when two arguments
# follow; otherwise the letter is a variable, and C(x + 1) is still C·(x + 1).
COUNTING: dict[str, tuple[int, int]] = {"C": (2, 2), "A": (2, 2)}

# The name of n! in the tree: it is written after its argument, never typed as a name.
FACTORIAL = "factorial"

CONSTANTS = frozenset({"pi", "e"})

TRIGONOMETRIC = frozenset({"sin", "cos", "tan", "sec", "csc", "cot"})

# Single letters that are not variables.
RESERVED: dict[str, str] = {
    "i": "Números complexos ainda não são suportados (o domínio é ℝ).",
}
