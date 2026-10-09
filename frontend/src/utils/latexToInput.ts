/**
 * What the visual editor drew (LaTeX) as the calculator's own syntax (Phase 11,
 * ADR 0020). The backend keeps receiving plain text and reading it with the safe
 * parser (ADR 0002): this is only a translation, shown to the user before it is
 * sent, and anything unknown is kept as typed so the parser can explain it.
 */

const FUNCTIONS: Record<string, string> = {
  sin: "sin",
  cos: "cos",
  tan: "tan",
  sec: "sec",
  csc: "csc",
  cot: "cot",
  arcsin: "asin",
  arccos: "acos",
  arctan: "atan",
  ln: "ln",
  log: "log",
  exp: "exp",
};

const SYMBOLS: Record<string, string> = {
  pi: "pi",
  cdot: "*",
  times: "*",
  div: "/",
  degree: "°",
  circ: "°",
  infty: "inf",
  le: "<=",
  ge: ">=",
};

/** Commands that only space or size things: they become nothing. */
const IGNORED = new Set(["left", "right", "displaystyle", ",", ";", ":", "!", " ", "quad", "qquad"]);

class Reader {
  private index = 0;

  constructor(private readonly text: string) {}

  /** Reads until the end, or until an unmatched "}". */
  sequence(): string {
    let out = "";
    while (this.index < this.text.length) {
      const ch = this.text[this.index]!;
      if (ch === "}") {
        break;
      }
      out += this.item();
    }
    return out;
  }

  private item(): string {
    const ch = this.text[this.index]!;
    switch (ch) {
      case "\\":
        return this.command();
      case "{": {
        this.index += 1;
        const inner = this.sequence();
        this.index += 1; // the "}"
        return inner;
      }
      case "^": {
        this.index += 1;
        const exponent = this.argument();
        if (exponent === "°") {
          return "°"; // 30^{\circ}
        }
        return exponent.length === 1 ? `^${exponent}` : `^(${exponent})`;
      }
      case "_": {
        this.index += 1;
        this.argument(); // subscripts carry no meaning for the calculator
        return "";
      }
      case "~":
        this.index += 1;
        return " ";
      default:
        this.index += 1;
        return ch;
    }
  }

  /** The argument of ^, \frac, \sqrt: a group in braces, a command or one character. */
  private argument(): string {
    this.skipSpaces();
    const ch = this.text[this.index];
    if (ch === undefined) {
      return "";
    }
    if (ch === "{") {
      this.index += 1;
      const inner = this.sequence();
      this.index += 1;
      return inner;
    }
    if (ch === "\\") {
      return this.command();
    }
    this.index += 1;
    return ch;
  }

  private skipSpaces(): void {
    while (this.text[this.index] === " ") {
      this.index += 1;
    }
  }

  private command(): string {
    this.index += 1; // the backslash
    const start = this.index;
    if (/[a-zA-Z]/.test(this.text[this.index] ?? "")) {
      while (/[a-zA-Z]/.test(this.text[this.index] ?? "")) {
        this.index += 1;
      }
    } else {
      this.index += 1; // \, \; \{ ...
    }
    const name = this.text.slice(start, this.index);
    if (/^[a-zA-Z]+$/.test(name)) {
      this.skipSpaces(); // a space after a control word only ends its name
    }

    if (name === "left" || name === "right") {
      return this.delimiter(name);
    }
    if (IGNORED.has(name)) {
      return "";
    }
    switch (name) {
      case "frac":
      case "dfrac":
      case "tfrac": {
        const top = this.argument();
        const bottom = this.argument();
        return `(${top})/(${bottom})`;
      }
      case "sqrt": {
        this.skipSpaces();
        if (this.text[this.index] === "[") {
          const close = this.text.indexOf("]", this.index);
          const degree = new Reader(this.text.slice(this.index + 1, close)).sequence();
          this.index = close + 1;
          return `(${this.argument()})^(1/(${degree}))`;
        }
        return `sqrt(${this.argument()})`;
      }
      case "operatorname":
        return this.argument();
      case "mathrm":
      case "text":
        return this.argument();
      case "{":
        return "(";
      case "}":
        return ")";
      case "lbrack":
        return "[";
      case "rbrack":
        return "]";
      default:
        if (name in FUNCTIONS) {
          return this.function(FUNCTIONS[name]!);
        }
        if (name in SYMBOLS) {
          return SYMBOLS[name]!;
        }
        return `\\${name}`; // unknown: the parser will say so
    }
  }

  /** The inside of (…) or \left(…\right), without the outer parentheses. */
  private parenthesized(): string {
    let depth = 0;
    let out = "";
    while (this.index < this.text.length) {
      const piece = this.item();
      if (piece.endsWith("(")) {
        depth += 1;
        if (depth === 1) {
          continue;
        }
      } else if (piece === ")") {
        depth -= 1;
        if (depth === 0) {
          return out;
        }
      }
      out += piece;
    }
    return out;
  }

  /** \left( and \right]: the delimiter itself; |x| (\left| or \vert) is abs(x). */
  private delimiter(side: "left" | "right"): string {
    this.skipSpaces();
    let ch = this.text[this.index] ?? "";
    if (ch === "\\") {
      const start = this.index + 1;
      this.index = start;
      while (/[a-zA-Z]/.test(this.text[this.index] ?? "")) {
        this.index += 1;
      }
      if (this.index === start) {
        this.index += 1;
      }
      const name = this.text.slice(start, this.index);
      this.skipSpaces();
      const named: Record<string, string> = { vert: "|", lvert: "|", rvert: "|", "{": "(", "}": ")" };
      ch = named[name] ?? "";
    } else {
      this.index += 1;
    }
    if (ch === "|") {
      return side === "left" ? "abs(" : ")";
    }
    return ch === "." ? "" : ch;
  }

  /** sin(x) as typed; \sin x (no parentheses) gets them: sin(x); \log_{2}(8) is log(8; 2). */
  private function(name: string): string {
    this.skipSpaces();
    if (name === "log" && this.text[this.index] === "_") {
      this.index += 1;
      const base = this.argument();
      this.skipSpaces();
      const grouped = this.text.startsWith("\\left(", this.index) || this.text[this.index] === "(";
      const value = grouped ? this.parenthesized() : this.argument();
      return `log(${value}; ${base})`;
    }
    const next = this.text.slice(this.index, this.index + 5);
    if (next.startsWith("(") || next.startsWith("\\left")) {
      return name;
    }
    if (next.startsWith("^")) {
      return name; // sin^2(x) stays for the parser to explain
    }
    return `${name}(${this.argument()})`;
  }
}

export function latexToInput(latex: string): string {
  const text = new Reader(latex.trim()).sequence();
  // Function names glued to what follows read better with parentheses kept as typed:
  // only spaces are normalized.
  return text.replace(/\s+/g, " ").trim();
}
