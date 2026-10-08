/**
 * Mirrors `MathResult` in backend/app/models/result.py (docs/architecture.md, §4).
 * Keep both in sync: the fixtures in src/test/fixtures are real API responses.
 */

export type IntentName =
  | "arithmetic"
  | "simplify"
  | "factor"
  | "expand"
  | "solve_equation"
  | "solve_system"
  | "polynomial_division"
  | "derivative"
  | "integral"
  | "limit"
  | "graph"
  | "statistics"
  | "matrix"
  | "vector"
  | "geometry"
  | "probability";

export type VerificationStatus =
  | "verified_symbolic"
  | "verified_numeric"
  | "partial"
  | "unverified"
  | "not_applicable"
  | "failed";

export interface ResultValue {
  plain: string;
  latex: string;
  approx: string | null;
}

export interface Step {
  description: string;
  latex: string | null;
}

/** The strategy behind one check (ADR 0010). */
export type CheckKind =
  | "symbolic"
  | "substitution"
  | "numeric"
  | "comparison"
  | "completeness"
  | "domain"
  | "execution";

export type CheckOutcome = "passed" | "failed" | "inconclusive";

/** Why a result is only partially verified, or not verified at all. */
export type ReasonCode =
  | "completeness_not_proved"
  | "numeric_evidence_only"
  | "few_points"
  | "too_large"
  | "inconclusive"
  | "no_strategy"
  | "deadline"
  | "internal_error";

export interface VerificationCheck {
  kind: CheckKind;
  outcome: CheckOutcome;
  message: string;
}

export interface VerificationReport {
  status: VerificationStatus;
  /** The strategies used, in the order they first appear in `checks`. */
  methods: CheckKind[];
  checks: VerificationCheck[];
  message: string;
  /** Set for `partial` and `unverified` only. */
  reason: ReasonCode | null;
}

export interface ResultWarning {
  code: string;
  message: string;
}

export interface ResultError {
  code: string;
  message: string;
  /** Index into `MathResult.input` (the text the user typed). */
  position: number | null;
}

/** How a request in words was read (docs/architecture.md, §4). */
export interface Interpretation {
  /** "rules": the local rules; "ai": an AI model, which only translated the phrase. */
  method: "rules" | "ai";
  intent: IntentName | null;
  /** The math text that was calculated. */
  expression: string;
  options: Record<string, string | number>;
  provider: string | null;
  model: string | null;
}

export interface MathResult {
  success: boolean;
  intent: IntentName | null;
  input: string;
  normalized_input: string | null;
  result: ResultValue | null;
  steps: Step[];
  details: Record<string, unknown>;
  verification: VerificationReport | null;
  warnings: ResultWarning[];
  error: ResultError | null;
  /** Null for plain math; set when the input was a phrase. */
  interpretation: Interpretation | null;
}

const INTENTS: readonly string[] = [
  "arithmetic",
  "simplify",
  "factor",
  "expand",
  "solve_equation",
  "solve_system",
  "polynomial_division",
  "derivative",
  "integral",
  "limit",
  "graph",
  "statistics",
  "matrix",
  "vector",
  "geometry",
  "probability",
];
const STATUSES: readonly string[] = [
  "verified_symbolic",
  "verified_numeric",
  "partial",
  "unverified",
  "not_applicable",
  "failed",
];

const KINDS: readonly string[] = [
  "symbolic",
  "substitution",
  "numeric",
  "comparison",
  "completeness",
  "domain",
  "execution",
];
const OUTCOMES: readonly string[] = ["passed", "failed", "inconclusive"];
const REASONS: readonly string[] = [
  "completeness_not_proved",
  "numeric_evidence_only",
  "few_points",
  "too_large",
  "inconclusive",
  "no_strategy",
  "deadline",
  "internal_error",
];

type Data = Record<string, unknown>;

const isObject = (value: unknown): value is Data =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const isString = (value: unknown): value is string => typeof value === "string";
const isNullableString = (value: unknown) => value === null || isString(value);
const isArrayOf = <T>(value: unknown, check: (item: unknown) => item is T): value is T[] =>
  Array.isArray(value) && value.every(check);

const isMessage = (value: unknown): value is ResultWarning =>
  isObject(value) && isString(value.code) && isString(value.message);

const isResultValue = (value: unknown): value is ResultValue =>
  isObject(value) && isString(value.plain) && isString(value.latex) && isNullableString(value.approx);

const isStep = (value: unknown): value is Step =>
  isObject(value) && isString(value.description) && isNullableString(value.latex);

const isOneOf = (options: readonly string[]) => (value: unknown) =>
  isString(value) && options.includes(value);

const isCheck = (value: unknown): value is VerificationCheck =>
  isObject(value) &&
  isOneOf(KINDS)(value.kind) &&
  isOneOf(OUTCOMES)(value.outcome) &&
  isString(value.message);

const isVerification = (value: unknown): value is VerificationReport =>
  isObject(value) &&
  isOneOf(STATUSES)(value.status) &&
  isArrayOf(value.methods, (kind): kind is CheckKind => isOneOf(KINDS)(kind)) &&
  isArrayOf(value.checks, isCheck) &&
  value.checks.length > 0 &&
  isString(value.message) &&
  (value.reason === null || isOneOf(REASONS)(value.reason));

const isError = (value: unknown): value is ResultError =>
  isObject(value) &&
  isString(value.code) &&
  isString(value.message) &&
  (value.position === null || typeof value.position === "number");

const isIntent = (value: unknown) => isString(value) && INTENTS.includes(value);

const isInterpretation = (value: unknown): value is Interpretation =>
  isObject(value) &&
  (value.method === "rules" || value.method === "ai") &&
  (value.intent === null || isIntent(value.intent)) &&
  isString(value.expression) &&
  isObject(value.options) &&
  Object.values(value.options).every((option) => isString(option) || typeof option === "number") &&
  isNullableString(value.provider) &&
  isNullableString(value.model);

/** Runtime check of an API response: the frontend never trusts the shape blindly. */
export function isMathResult(value: unknown): value is MathResult {
  if (!isObject(value)) {
    return false;
  }
  const shapeOk =
    typeof value.success === "boolean" &&
    (value.intent === null || isIntent(value.intent)) &&
    isString(value.input) &&
    isNullableString(value.normalized_input) &&
    (value.result === null || isResultValue(value.result)) &&
    isArrayOf(value.steps, isStep) &&
    isObject(value.details) &&
    (value.verification === null || isVerification(value.verification)) &&
    isArrayOf(value.warnings, isMessage) &&
    (value.error === null || isError(value.error)) &&
    (value.interpretation === null || isInterpretation(value.interpretation));
  if (!shapeOk) {
    return false;
  }
  // Same consistency rule as the backend model.
  return value.success
    ? value.result !== null && value.verification !== null && value.error === null
    : value.result === null && value.error !== null;
}
