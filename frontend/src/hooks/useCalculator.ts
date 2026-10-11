import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, calculate } from "../services/api";
import type { IntentName, MathResult } from "../types/math";
import type { CalculationOptions } from "../utils/operations";

export type CalculatorState =
  | { status: "idle" }
  | { status: "loading" }
  /** `live`: calculated while typing, so an error is only a hint (ADR 0023). */
  | { status: "done"; result: MathResult; live: boolean }
  /** No MathResult at all: the API could not be reached or answered nonsense. */
  | { status: "failed"; message: string };

export function useCalculator() {
  const [state, setState] = useState<CalculatorState>({ status: "idle" });
  /** A live calculation is running: the last result stays, dimmed, until it arrives. */
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const submit = useCallback(
    async (
      input: string,
      intent: IntentName | null = null,
      options: CalculationOptions | null = null,
      allowAi = false,
      live = false,
    ): Promise<MathResult | null> => {
      controller.current?.abort();
      const current = new AbortController();
      controller.current = current;
      setBusy(live);
      if (!live) {
        setState({ status: "loading" });
      }

      try {
        const result = await calculate(input, intent, options, allowAi, current.signal);
        if (!current.signal.aborted) {
          setBusy(false);
          setState({ status: "done", result, live });
          return result;
        }
      } catch (error: unknown) {
        if (current.signal.aborted) {
          return null;
        }
        const message =
          error instanceof ApiError ? error.message : "Não foi possível conectar à API.";
        setBusy(false);
        setState({ status: "failed", message });
      }
      return null;
    },
    [],
  );

  /** Back to the empty screen (the input was cleared); drops a calculation in flight. */
  const reset = useCallback(() => {
    controller.current?.abort();
    setBusy(false);
    setState({ status: "idle" });
  }, []);

  return { state, submit, busy, reset };
}
