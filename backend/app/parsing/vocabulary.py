"""The closed list of names the parser accepts. Anything else is rejected."""

# Canonical function name -> (minimum, maximum) number of arguments.
FUNCTIONS: dict[str, tuple[int, int]] = {
    "sqrt": (1, 1),
    "abs": (1, 1),
    "sin": (1, 1),
    "cos": (1, 1),
    "tan": (1, 1),
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
}

CONSTANTS = frozenset({"pi", "e"})

TRIGONOMETRIC = frozenset({"sin", "cos", "tan"})

# Single letters that are not variables.
RESERVED: dict[str, str] = {
    "i": "Números complexos ainda não são suportados (o domínio é ℝ).",
}
