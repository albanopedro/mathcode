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
    <div role="group" aria-label="Tema" className="flex rounded-lg border border-slate-300 text-xs">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={choice === option.value}
          onClick={() => choose(option.value)}
          className={`px-2.5 py-1 first:rounded-l-lg last:rounded-r-lg ${
            choice === option.value
              ? "bg-slate-900 text-white"
              : "text-slate-700 hover:bg-slate-100"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
