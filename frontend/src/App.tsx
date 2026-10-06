import { ApiStatus } from "./components/ApiStatus";
import { Calculator } from "./components/Calculator";

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <main className="mx-auto flex max-w-2xl flex-col gap-8 px-4 py-12 sm:py-16">
        <header className="flex flex-col gap-2">
          <h1 className="text-4xl font-semibold tracking-tight">Mathcode</h1>
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
