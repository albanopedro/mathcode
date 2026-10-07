import type { FieldValues, Operation } from "../utils/operations";

interface OperationFieldsProps {
  operation: Operation;
  values: FieldValues;
  onChange: (values: FieldValues) => void;
}

const INPUT_CLASS =
  "rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-mono text-sm shadow-sm focus:border-slate-500 focus:ring-2 focus:ring-slate-200 focus:outline-none";
const LABEL_CLASS = "flex flex-col gap-1 text-sm font-medium text-slate-700";

/** The extra inputs of the chosen operation (calculus): only those it uses. */
export function OperationFields({ operation, values, onChange }: OperationFieldsProps) {
  if (operation.fields.length === 0) {
    return null;
  }
  const set = (patch: Partial<FieldValues>) => onChange({ ...values, ...patch });
  const has = (field: Operation["fields"][number]) => operation.fields.includes(field);

  return (
    <fieldset className="flex flex-wrap items-end gap-3">
      <legend className="sr-only">Parâmetros de {operation.label}</legend>
      {has("variable") && (
        <label className={LABEL_CLASS}>
          Variável
          <input
            type="text"
            value={values.variable}
            onChange={(event) => set({ variable: event.target.value })}
            placeholder="auto"
            autoComplete="off"
            className={`${INPUT_CLASS} w-20`}
          />
        </label>
      )}
      {has("order") && (
        <label className={LABEL_CLASS}>
          Ordem
          <input
            type="number"
            inputMode="numeric"
            min={1}
            max={10}
            value={values.order}
            onChange={(event) => set({ order: event.target.value })}
            className={`${INPUT_CLASS} w-20`}
          />
        </label>
      )}
      {has("bounds") && (
        <>
          <label className={LABEL_CLASS}>
            De
            <input
              type="text"
              value={values.lower}
              onChange={(event) => set({ lower: event.target.value })}
              placeholder="ex.: 0"
              autoComplete="off"
              className={`${INPUT_CLASS} w-28`}
            />
          </label>
          <label className={LABEL_CLASS}>
            Até
            <input
              type="text"
              value={values.upper}
              onChange={(event) => set({ upper: event.target.value })}
              placeholder="ex.: inf"
              autoComplete="off"
              className={`${INPUT_CLASS} w-28`}
            />
          </label>
          <p className="basis-full text-xs text-slate-500">
            Sem limites, a integral é indefinida. Use inf para infinito.
          </p>
        </>
      )}
      {has("point") && (
        <label className={LABEL_CLASS}>
          Ponto
          <input
            type="text"
            value={values.point}
            onChange={(event) => set({ point: event.target.value })}
            placeholder="0, pi/2 ou inf"
            autoComplete="off"
            className={`${INPUT_CLASS} w-36`}
          />
        </label>
      )}
      {has("side") && (
        <label className={LABEL_CLASS}>
          Lado
          <select
            value={values.side}
            onChange={(event) => set({ side: event.target.value as FieldValues["side"] })}
            className={INPUT_CLASS}
          >
            <option value="both">Os dois lados</option>
            <option value="left">Pela esquerda</option>
            <option value="right">Pela direita</option>
          </select>
        </label>
      )}
    </fieldset>
  );
}
