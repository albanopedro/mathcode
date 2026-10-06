/** Mirrors `HealthResponse` in backend/app/models/health.py. */
export type Environment = "development" | "test" | "production";

export interface HealthResponse {
  status: "ok";
  version: string;
  environment: Environment;
}

const ENVIRONMENTS: readonly string[] = ["development", "test", "production"];

export function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const data = value as Record<string, unknown>;
  return (
    data.status === "ok" &&
    typeof data.version === "string" &&
    typeof data.environment === "string" &&
    ENVIRONMENTS.includes(data.environment)
  );
}
