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
  | "graph";

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

export interface VerificationReport {
  status: VerificationStatus;
  method: string;
  checks: string[];
  message: string;
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
];
const STATUSES: readonly string[] = [
  "verified_symbolic",
  "verified_numeric",
  "partial",
  "unverified",
  "not_applicable",
  "failed",
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

const isVerification = (value: unknown): value is VerificationReport =>
  isObject(value) &&
  isString(value.status) &&
  STATUSES.includes(value.status) &&
  isString(value.method) &&
  isArrayOf(value.checks, isString) &&
  isString(value.message);

const isError = (value: unknown): value is ResultError =>
  isObject(value) &&
  isString(value.code) &&
  isString(value.message) &&
  (value.position === null || typeof value.position === "number");

/** Runtime check of an API response: the frontend never trusts the shape blindly. */
export function isMathResult(value: unknown): value is MathResult {
  if (!isObject(value)) {
    return false;
  }
  const shapeOk =
    typeof value.success === "boolean" &&
    (value.intent === null || (isString(value.intent) && INTENTS.includes(value.intent))) &&
    isString(value.input) &&
    isNullableString(value.normalized_input) &&
    (value.result === null || isResultValue(value.result)) &&
    isArrayOf(value.steps, isStep) &&
    isObject(value.details) &&
    (value.verification === null || isVerification(value.verification)) &&
    isArrayOf(value.warnings, isMessage) &&
    (value.error === null || isError(value.error));
  if (!shapeOk) {
    return false;
  }
  // Same consistency rule as the backend model.
  return value.success
    ? value.result !== null && value.verification !== null && value.error === null
    : value.result === null && value.error !== null;
}
