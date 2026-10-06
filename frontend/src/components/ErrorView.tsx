import type { MathResult, ResultError } from "../types/math";
import { Verification } from "./Verification";

interface ErrorViewProps {
  result: MathResult;
  error: ResultError;
}

export function ErrorView({ result, error }: ErrorViewProps) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-xl border border-rose-200 bg-rose-50 p-5 text-rose-900"
    >
      <h2 className="font-medium">Não foi possível calcular</h2>
      <p>{error.message}</p>
      {error.position !== null && <InputMarker input={result.input} position={error.position} />}
      {result.verification && <Verification report={result.verification} />}
    </div>
  );
}

/** Shows the input with the character at ``position`` highlighted. */
function InputMarker({ input, position }: { input: string; position: number }) {
  // The API counts Unicode code points (Python), not UTF-16 units: split accordingly.
  const chars = Array.from(input);
  const before = chars.slice(0, position).join("");
  const at = chars[position] ?? "";
  const after = chars.slice(position + 1).join("");

  return (
    <p className="overflow-x-auto rounded-lg bg-white px-3 py-2 font-mono whitespace-pre text-slate-800">
      {before}
      <mark className="rounded-sm bg-rose-200 text-rose-950">{at === "" ? " " : at}</mark>
      {after}
      <span className="sr-only"> (problema no caractere {position + 1})</span>
    </p>
  );
}
