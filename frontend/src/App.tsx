import { ApiStatus } from "./components/ApiStatus";
import { Calculator } from "./components/Calculator";
import { ThemeSelector } from "./components/ThemeSelector";

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <main className="mx-auto flex max-w-2xl flex-col gap-8 px-4 py-12 sm:py-16">
        <a
          href="#result-area"
          className="sr-only rounded-lg bg-slate-900 px-3 py-2 text-white focus:not-sr-only focus:absolute focus:top-2 focus:left-2"
        >
          Pular para o resultado
        </a>
        <header className="flex flex-col gap-2">
          <div className="flex items-start justify-between gap-3">
            <h1 className="text-4xl font-semibold tracking-tight">Mathcode</h1>
            <ThemeSelector />
          </div>
          <p className="text-lg text-slate-600">
            Calculadora matemática com resultados verificados.
          </p>
        </header>

        <Calculator />

        <footer className="border-t border-slate-200 pt-6">
          <ApiStatus />
        </footer>
      </main>
    </div>
  );
}
