import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, calculate } from "../services/api";
import type { IntentName, MathResult } from "../types/math";
import type { CalculationOptions } from "../utils/operations";

export type CalculatorState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "done"; result: MathResult }
  /** No MathResult at all: the API could not be reached or answered nonsense. */
  | { status: "failed"; message: string };

export function useCalculator() {
  const [state, setState] = useState<CalculatorState>({ status: "idle" });
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const submit = useCallback(
    async (
      input: string,
      intent: IntentName | null = null,
      options: CalculationOptions | null = null,
      allowAi = false,
    ) => {
      controller.current?.abort();
      const current = new AbortController();
      controller.current = current;
      setState({ status: "loading" });

      try {
        const result = await calculate(input, intent, options, allowAi, current.signal);
        if (!current.signal.aborted) {
          setState({ status: "done", result });
        }
      } catch (error: unknown) {
        if (current.signal.aborted) {
          return;
        }
        const message =
          error instanceof ApiError ? error.message : "Não foi possível conectar à API.";
        setState({ status: "failed", message });
      }
    },
    [],
  );

  return { state, submit };
}
