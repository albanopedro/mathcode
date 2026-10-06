import { type HealthResponse, isHealthResponse } from "../types/health";
import { isMathResult, type MathResult } from "../types/math";

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
 */
export async function calculate(input: string, signal?: AbortSignal): Promise<MathResult> {
  const response = await fetch("/api/calculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
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
