import { ApiStatus } from "./components/ApiStatus";

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <main className="mx-auto flex max-w-2xl flex-col gap-8 px-4 py-16">
        <header className="flex flex-col gap-2">
          <h1 className="text-4xl font-semibold tracking-tight">Mathcode</h1>
          <p className="text-lg text-slate-600">
            Calculadora matemática com resultados verificados.
          </p>
        </header>

        <ApiStatus />

        <p className="text-sm text-slate-500">
          Em construção: a calculadora chega nas próximas fases.
        </p>
      </main>
    </div>
  );
}
