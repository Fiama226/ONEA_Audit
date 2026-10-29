import { useId } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";
import { useAuditPlanSummary } from "../api";
import { formatDays } from "../format";
import { quarterLabel } from "../labels";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="grid gap-0.5">
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

/** Synthèse d'un programme : comptes et charge, jamais de pourcentage. */
export function PlanSummary({ planId }: { planId: string }) {
  const p = fr.programmation;
  const c = fr.programmationPlans;
  const titleId = useId();
  const summary = useAuditPlanSummary(planId);
  const data = summary.data;

  return (
    <section aria-labelledby={titleId} className="grid gap-3">
      <h2 id={titleId} className="text-base font-semibold">
        {c.summaryTitle}
      </h2>
      {summary.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {c.summaryLoadError}
        </p>
      ) : !data ? (
        <Skeleton className="h-16 w-full" />
      ) : (
        <div className="grid gap-4 rounded-lg border border-border bg-surface p-4">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label={p.lineCount} value={data.nb_lignes} />
            <Stat label={c.totalLoadColumn} value={formatDays(data.charge_totale_jours)} />
            <Stat label={c.assurance} value={data.par_type.ASSURANCE ?? 0} />
            <Stat label={c.conseil} value={data.par_type.CONSEIL ?? 0} />
          </dl>
          <div>
            <h3 className="mb-2 text-xs text-text-muted">{c.byQuarter}</h3>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[1, 2, 3, 4].map((q) => (
                <Stat
                  key={q}
                  label={quarterLabel(q)}
                  value={(data.par_trimestre as Record<string, number>)[String(q)] ?? 0}
                />
              ))}
            </dl>
          </div>
        </div>
      )}
    </section>
  );
}
