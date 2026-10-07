import { type HealthResponse, isHealthResponse } from "../types/health";
import { type IntentName, isMathResult, type MathResult } from "../types/math";
import type { CalculationOptions } from "../utils/operations";

export class ApiError extends Error {
  override name = "ApiError";
}

// Gateway errors: in development, Vite's proxy answers 502 when the backend
// is not running, so these mean "unreachable" rather than "the API failed".
const UNREACHABLE_STATUSES = new Set([502, 503, 504]);

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch("/api/health", { signal });
  if (UNREACHABLE_STATUSES.has(response.status)) {
    throw new ApiError(`Não foi possível conectar à API (HTTP ${response.status}).`);
  }
  if (!response.ok) {
    throw new ApiError(`A API respondeu com HTTP ${response.status}.`);
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new ApiError("A API respondeu com algo que não é JSON.");
  }
  if (!isHealthResponse(data)) {
    throw new ApiError("A API respondeu num formato inesperado.");
  }
  return data;
}

/**
 * Asks the API to calculate. Every answer of the API is a MathResult, also on
 * HTTP 500 and 503 (docs/architecture.md, §5), so the body decides, not the status.
 *
 * `allowAi` lets the API send a phrase its rules do not understand to an AI
 * model (ADR 0009); it only applies without an intent.
 */
export async function calculate(
  input: string,
  intent: IntentName | null = null,
  options: CalculationOptions | null = null,
  allowAi = false,
  signal?: AbortSignal,
): Promise<MathResult> {
  // Without an intent, the API detects the operation from the input.
  const body: Record<string, unknown> = { input };
  if (intent) {
    body.intent = intent;
  }
  if (options) {
    body.options = options;
  }
  if (allowAi) {
    body.allow_ai = true;
  }
  const response = await fetch("/api/calculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    data = undefined;
  }
  if (isMathResult(data)) {
    return data;
  }
  if (UNREACHABLE_STATUSES.has(response.status)) {
    throw new ApiError(`Não foi possível conectar à API (HTTP ${response.status}).`);
  }
  if (response.status === 422) {
    throw new ApiError("A API recusou o pedido por formato inválido (HTTP 422).");
  }
  throw new ApiError(`A API respondeu num formato inesperado (HTTP ${response.status}).`);
}
