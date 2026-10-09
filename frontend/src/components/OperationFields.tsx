import { FIGURE_GROUPS, FIGURES, figure } from "../utils/geometry";
import { TRIG_CALCULATIONS, trigCalculation } from "../utils/trigonometry";
import {
  PROBABILITY_CALCULATIONS,
  PROBABILITY_GROUPS,
  probabilityCalculation,
} from "../utils/probability";
import {
  type FieldValues,
  MATRIX_OPERATIONS,
  type Operation,
  VECTOR_OPERATIONS,
} from "../utils/operations";

interface OperationFieldsProps {
  operation: Operation;
  values: FieldValues;
  onChange: (values: FieldValues) => void;
}

const INPUT_CLASS =
  "rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-mono text-sm shadow-sm focus:border-slate-500 focus:ring-2 focus:ring-slate-200 focus:outline-none";
const LABEL_CLASS = "flex flex-col gap-1 text-sm font-medium text-slate-700";

/** The extra inputs of the chosen operation: only those it uses. */
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
      {has("interval") && (
        <>
          <label className={LABEL_CLASS}>
            Soluções de
            <input
              type="text"
              value={values.lower}
              onChange={(event) => set({ lower: event.target.value })}
              placeholder="0"
              autoComplete="off"
              className={`${INPUT_CLASS} w-28`}
            />
          </label>
          <label className={LABEL_CLASS}>
            até
            <input
              type="text"
              value={values.upper}
              onChange={(event) => set({ upper: event.target.value })}
              placeholder="2pi"
              autoComplete="off"
              className={`${INPUT_CLASS} w-28`}
            />
          </label>
          <p className="basis-full text-xs text-slate-500">
            Para equações com infinitas soluções, como sin(x) = 1/2: onde listá-las. Vazios: de 0
            a 2π.
          </p>
        </>
      )}
      {has("trig_calculation") && (
        <>
          <label className={LABEL_CLASS}>
            Cálculo
            <select
              value={values.trig_calculation}
              onChange={(event) => set({ trig_calculation: event.target.value })}
              className={INPUT_CLASS}
            >
              {TRIG_CALCULATIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <p className="basis-full text-sm text-slate-500">
            Entrada: {trigCalculation(values.trig_calculation).input}. Ex.:{" "}
            <code className="font-mono text-slate-700">
              {trigCalculation(values.trig_calculation).example}
            </code>
          </p>
        </>
      )}
      {has("x_range") && (
        <>
          <label className={LABEL_CLASS}>
            x de
            <input
              type="text"
              value={values.x_min}
              onChange={(event) => set({ x_min: event.target.value })}
              placeholder="-10"
              autoComplete="off"
              className={`${INPUT_CLASS} w-28`}
            />
          </label>
          <label className={LABEL_CLASS}>
            x até
            <input
              type="text"
              value={values.x_max}
              onChange={(event) => set({ x_max: event.target.value })}
              placeholder="10"
              autoComplete="off"
              className={`${INPUT_CLASS} w-28`}
            />
          </label>
          <p className="basis-full text-xs text-slate-500">
            Vazios: de -10 a 10. Aceitam expressões como -2pi. Várias funções: separe com ;.
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
      {has("matrix_operation") && (
        <label className={LABEL_CLASS}>
          Cálculo
          <select
            value={values.matrix_operation}
            onChange={(event) =>
              set({ matrix_operation: event.target.value as FieldValues["matrix_operation"] })
            }
            className={INPUT_CLASS}
          >
            {MATRIX_OPERATIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      )}
      {has("geometry") && (
        <>
          <label className={LABEL_CLASS}>
            Figura
            <select
              value={values.geometry_figure}
              onChange={(event) => {
                const chosen = figure(event.target.value);
                set({
                  geometry_figure: chosen.value,
                  geometry_calculation: chosen.calculations[0]!.value,
                });
              }}
              className={INPUT_CLASS}
            >
              {FIGURE_GROUPS.map((group) => (
                <optgroup key={group} label={group}>
                  {FIGURES.filter((option) => option.group === group).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
          <label className={LABEL_CLASS}>
            Cálculo
            <select
              value={values.geometry_calculation}
              onChange={(event) => set({ geometry_calculation: event.target.value })}
              className={INPUT_CLASS}
            >
              {figure(values.geometry_figure).calculations.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <p className="basis-full text-sm text-slate-500">
            Medidas: {figure(values.geometry_figure).measures}. Ex.:{" "}
            <code className="font-mono text-slate-700">
              {figure(values.geometry_figure).example}
            </code>
          </p>
        </>
      )}
      {has("probability") && (
        <>
          <label className={LABEL_CLASS}>
            Cálculo
            <select
              value={values.probability_calculation}
              onChange={(event) => set({ probability_calculation: event.target.value })}
              className={INPUT_CLASS}
            >
              {PROBABILITY_GROUPS.map((group) => (
                <optgroup key={group} label={group}>
                  {PROBABILITY_CALCULATIONS.filter((option) => option.group === group).map(
                    (option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ),
                  )}
                </optgroup>
              ))}
            </select>
          </label>
          <p className="basis-full text-sm text-slate-500">
            Valores: {probabilityCalculation(values.probability_calculation).values}. Ex.:{" "}
            <code className="font-mono text-slate-700">
              {probabilityCalculation(values.probability_calculation).example}
            </code>
          </p>
        </>
      )}
      {has("vector_operation") && (
        <label className={LABEL_CLASS}>
          Cálculo
          <select
            value={values.vector_operation}
            onChange={(event) =>
              set({ vector_operation: event.target.value as FieldValues["vector_operation"] })
            }
            className={INPUT_CLASS}
          >
            {VECTOR_OPERATIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      )}
    </fieldset>
  );
}
