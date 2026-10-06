import type { VerificationReport, VerificationStatus } from "../types/math";

// The headline is the backend message; the status only picks icon and colors.
const BADGES: Record<VerificationStatus, { icon: string; className: string }> = {
  verified_symbolic: {
    icon: "✓",
    className: "border-emerald-200 bg-emerald-50 text-emerald-800",
  },
  verified_numeric: {
    icon: "✓",
    className: "border-emerald-200 bg-emerald-50 text-emerald-800",
  },
  partial: {
    icon: "!",
    className: "border-amber-200 bg-amber-50 text-amber-800",
  },
  unverified: {
    icon: "?",
    className: "border-amber-200 bg-amber-50 text-amber-800",
  },
  not_applicable: {
    icon: "–",
    className: "border-slate-200 bg-slate-50 text-slate-700",
  },
  failed: {
    icon: "✗",
    className: "border-rose-200 bg-rose-50 text-rose-800",
  },
};

export function Verification({ report }: { report: VerificationReport }) {
  const badge = BADGES[report.status];
  return (
    <div className={`rounded-lg border px-4 py-3 ${badge.className}`}>
      <p className="flex items-baseline gap-2 font-medium">
        <span aria-hidden="true">{badge.icon}</span>
        {report.message}
      </p>
      {report.checks.length > 0 && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer select-none font-medium">Como foi verificado</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {report.checks.map((check) => (
              <li key={check}>{check}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
