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

# Values in one statistics request (Phase 10); "1;" repeated fits 250 in 500 characters.
MAX_DATA_VALUES = 200

# Rows and columns of a matrix (Phase 10, ADR 0012).
MAX_MATRIX_SIZE = 8

# Highest derivative order.
MAX_DERIVATIVE_ORDER = 10

# Graphs: functions drawn together, and samples per function.
MAX_GRAPH_FUNCTIONS = 5
GRAPH_SAMPLES = 801
# Widest x range accepted, so that the samples still mean something.
MAX_GRAPH_WIDTH = 10**6
