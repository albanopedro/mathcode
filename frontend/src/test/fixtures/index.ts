/**
 * Real responses of POST /api/calculate, captured from the running backend.
 * They keep the frontend types honest: if the backend changes the shape,
 * re-capture them (one POST per file, with the API running) and the type
 * guard tests will say what broke.
 */
import type { MathResult } from "../../types/math";
import allReals from "./all-reals.json";
import allRealsExcept from "./all-reals-except.json";
import arithmetic from "./arithmetic.json";
import complexOmitted from "./complex-omitted.json";
import division from "./division.json";
import divisionByZero from "./division-by-zero.json";
import doubleRoot from "./double-root.json";
import equation from "./equation.json";
import expand from "./expand.json";
import factor from "./factor.json";
import factorUnchanged from "./factor-unchanged.json";
import noSolution from "./no-solution.json";
import parseError from "./parse-error.json";
import partial from "./partial.json";
import primeFactors from "./prime-factors.json";
import quadratic from "./quadratic.json";
import simplifyDomain from "./simplify-domain.json";
import systemInfinite from "./system-infinite.json";
import systemNone from "./system-none.json";
import systemUnique from "./system-unique.json";
import timeout from "./timeout.json";
import unverified from "./unverified.json";
import warnings from "./warnings.json";

const raw = {
  allReals,
  allRealsExcept,
  arithmetic,
  complexOmitted,
  division,
  divisionByZero,
  doubleRoot,
  equation,
  expand,
  factor,
  factorUnchanged,
  noSolution,
  parseError,
  partial,
  primeFactors,
  quadratic,
  simplifyDomain,
  systemInfinite,
  systemNone,
  systemUnique,
  timeout,
  unverified,
  warnings,
};

export const fixtures = raw as unknown as Record<keyof typeof raw, MathResult>;

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
