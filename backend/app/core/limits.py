"""Hard limits that keep a single calculation from exhausting the server (ADR 0002)."""

MAX_INPUT_LENGTH = 500

# Nesting of parentheses, powers and signs. Long flat sums are bounded by the
# input length instead.
MAX_NESTING = 100

# Digits of an exact number. Kept below Python's own 4300-digit guard on
# int <-> str conversion, so every accepted result can still be printed.
MAX_RESULT_DIGITS = 4000

# Largest integer exponent applied to a symbolic base, as in (x + 1)^1000.
MAX_SYMBOLIC_EXPONENT = 1000

# Equations in a system, and unknowns in it.
MAX_SYSTEM_EQUATIONS = 10

# Highest derivative order.
MAX_DERIVATIVE_ORDER = 10
