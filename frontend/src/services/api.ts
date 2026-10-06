import { type HealthResponse, isHealthResponse } from "../types/health";

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
