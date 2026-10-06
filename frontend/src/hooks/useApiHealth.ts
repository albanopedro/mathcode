import { useCallback, useEffect, useState } from "react";

import { ApiError, fetchHealth } from "../services/api";
import type { HealthResponse } from "../types/health";

export type ApiHealthState =
  | { status: "checking" }
  | { status: "online"; health: HealthResponse }
  | { status: "offline"; reason: string };

export function useApiHealth() {
  const [state, setState] = useState<ApiHealthState>({ status: "checking" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    fetchHealth(controller.signal)
      .then((health) => setState({ status: "online", health }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        const reason =
          error instanceof ApiError ? error.message : "Não foi possível conectar à API.";
        setState({ status: "offline", reason });
      });

    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => {
    setState({ status: "checking" });
    setAttempt((n) => n + 1);
  }, []);

  return { state, retry };
}
