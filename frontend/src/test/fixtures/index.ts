/**
 * Real responses of POST /api/calculate, captured from the running backend.
 * They keep the frontend types honest: if the backend changes the shape,
 * re-capture them and the type guard tests will say what broke.
 */
import type { MathResult } from "../../types/math";
import allReals from "./all-reals.json";
import arithmetic from "./arithmetic.json";
import divisionByZero from "./division-by-zero.json";
import equation from "./equation.json";
import noSolution from "./no-solution.json";
import parseError from "./parse-error.json";
import simplifyDomain from "./simplify-domain.json";
import timeout from "./timeout.json";
import unverified from "./unverified.json";
import warnings from "./warnings.json";

export const fixtures = {
  allReals,
  arithmetic,
  divisionByZero,
  equation,
  noSolution,
  parseError,
  simplifyDomain,
  timeout,
  unverified,
  warnings,
} as unknown as Record<
  | "allReals"
  | "arithmetic"
  | "divisionByZero"
  | "equation"
  | "noSolution"
  | "parseError"
  | "simplifyDomain"
  | "timeout"
  | "unverified"
  | "warnings",
  MathResult
>;

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
