import { useApiHealth } from "../hooks/useApiHealth";

const ENVIRONMENT_LABELS = {
  development: "desenvolvimento",
  test: "teste",
  production: "produção",
} as const;

export function ApiStatus() {
  const { state, retry } = useApiHealth();

  return (
    <section
      aria-labelledby="api-status-title"
      className="card px-5 py-4"
    >
      <h2 id="api-status-title" className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
        Status da API
      </h2>

      <div role="status" className="mt-2 flex items-center gap-3 text-sm text-slate-700">
        {state.status === "checking" && (
          <>
            <Dot className="bg-slate-300" />
            <span>Verificando…</span>
          </>
        )}

        {state.status === "online" && (
          <>
            <Dot className="bg-emerald-500" />
            <span>
              Online · v{state.health.version} ·{" "}
              {ENVIRONMENT_LABELS[state.health.environment]}
            </span>
          </>
        )}

        {state.status === "offline" && (
          <>
            <Dot className="bg-rose-500" />
            <span>Offline: {state.reason}</span>
          </>
        )}
      </div>

      {state.status === "offline" && (
        <button
          type="button"
          onClick={retry}
          className="btn-secondary mt-4 px-3 py-1.5 text-sm"
        >
          Tentar de novo
        </button>
      )}
    </section>
  );
}

function Dot({ className }: { className: string }) {
  return <span aria-hidden="true" className={`size-2.5 shrink-0 rounded-full ${className}`} />;
}
