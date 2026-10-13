import { ApiStatus } from "./components/ApiStatus";
import { Calculator } from "./components/Calculator";
import { ThemeSelector } from "./components/ThemeSelector";

export default function App() {
  return (
    <div className="relative min-h-screen bg-slate-50 text-slate-900 antialiased">
      {/* A soft glow of the brand color behind the header; decoration only. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 -z-0 h-80 bg-gradient-to-b from-indigo-100/60 to-transparent"
      />
      <main className="relative mx-auto flex max-w-2xl flex-col gap-8 px-4 py-10 sm:py-14">
        <a
          href="#result-area"
          className="sr-only rounded-lg bg-slate-900 px-3 py-2 text-white focus:not-sr-only focus:absolute focus:top-2 focus:left-2"
        >
          Pular para o resultado
        </a>
        <header className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span
                aria-hidden="true"
                className="grid size-10 place-items-center rounded-xl bg-indigo-600 text-xl font-semibold text-white shadow-sm"
              >
                ∑
              </span>
              <h1 className="text-2xl font-semibold tracking-tight sm:text-4xl">Mathcode</h1>
            </div>
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
