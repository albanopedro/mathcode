/**
 * Real responses of POST /api/calculate, captured from the running backend.
 * They keep the frontend types honest: if the backend changes the shape,
 * re-capture them (one POST per file, with the API running) and the type
 * guard tests will say what broke.
 *
 * ai-equation came from the real free model (opencode/space-bunny-free).
 * ai-clarification is that model's real answer to "integral dupla de x",
 * replayed through the API with the mock provider (so it names "mock").
 * In Phase 9, both were re-captured by replaying those same answers (no new
 * AI call): only the verification changed, and ai-equation keeps the real
 * provider and model in its interpretation.
 */
import type { MathResult } from "../../types/math";
import aiClarification from "./ai-clarification.json";
import aiEquation from "./ai-equation.json";
import aiUnavailable from "./ai-unavailable.json";
import allReals from "./all-reals.json";
import allRealsExcept from "./all-reals-except.json";
import arithmetic from "./arithmetic.json";
import graphNoPoints from "./graph-no-points.json";
import graphParabola from "./graph-parabola.json";
import graphTan from "./graph-tan.json";
import graphTwo from "./graph-two.json";
import derivative from "./derivative.json";
import integralDefinite from "./integral-definite.json";
import integralDivergent from "./integral-divergent.json";
import integralIndefinite from "./integral-indefinite.json";
import invalidOrder from "./invalid-order.json";
import limitFinite from "./limit-finite.json";
import limitOneSided from "./limit-one-sided.json";
import limitOscillates from "./limit-oscillates.json";
import limitSides from "./limit-sides.json";
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
import phraseRules from "./phrase-rules.json";
import primeFactors from "./prime-factors.json";
import quadratic from "./quadratic.json";
import simplifyDomain from "./simplify-domain.json";
import statisticsNoMode from "./statistics-no-mode.json";
import statisticsPhrase from "./statistics-phrase.json";
import statisticsSingle from "./statistics-single.json";
import statisticsSummary from "./statistics-summary.json";
import systemInfinite from "./system-infinite.json";
import systemNone from "./system-none.json";
import systemUnique from "./system-unique.json";
import timeout from "./timeout.json";
import unverified from "./unverified.json";
import warnings from "./warnings.json";

const raw = {
  statisticsNoMode,
  statisticsPhrase,
  statisticsSingle,
  statisticsSummary,
  aiClarification,
  aiEquation,
  aiUnavailable,
  phraseRules,
  graphNoPoints,
  graphParabola,
  graphTan,
  graphTwo,
  derivative,
  integralDefinite,
  integralDivergent,
  integralIndefinite,
  invalidOrder,
  limitFinite,
  limitOneSided,
  limitOscillates,
  limitSides,
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
