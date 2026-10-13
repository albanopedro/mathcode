import { useTheme } from "../hooks/useTheme";
import type { ThemeChoice } from "../utils/theme";

const OPTIONS: readonly { value: ThemeChoice; label: string }[] = [
  { value: "system", label: "Sistema" },
  { value: "light", label: "Claro" },
  { value: "dark", label: "Escuro" },
];

/** Sistema / Claro / Escuro, remembered in this browser. */
export function ThemeSelector() {
  const { choice, choose } = useTheme();
  return (
    <div role="group" aria-label="Tema" className="flex rounded-full border border-slate-200 bg-white p-0.5 text-xs shadow-sm">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={choice === option.value}
          onClick={() => choose(option.value)}
          className={`rounded-full px-2.5 py-1 font-medium transition ${
            choice === option.value
              ? "bg-slate-900 text-white"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
