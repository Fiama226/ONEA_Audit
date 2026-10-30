import { DocumentSlot } from "@/features/communication/components/DocumentSlot";
import { fr } from "@/i18n/fr";
import type { SynthesePlan } from "../types";

const t = fr.planActions;

/** Avertissements non bloquants du plan et emplacement du document « Plan d'actions ». */
export function PlanSummary({ missionId, summary }: { missionId: string; summary: SynthesePlan }) {
  const warnings = [
    [t.warnNoFollowUp, summary.recommandations_sans_suite],
    [t.warnIncomplete, summary.actions_incompletes],
    [t.warnCommitments, summary.engagements_manquants],
  ] as const;
  const active = warnings.filter(([, list]) => list.length > 0);

  return (
    <section
      aria-labelledby="plan-summary-title"
      className="grid gap-3 rounded-md border border-border p-4 break-inside-avoid"
    >
      <h4 id="plan-summary-title" className="text-sm font-semibold">
        {t.summaryTitle}
      </h4>
      {active.length === 0 ? (
        <p className="text-sm text-text-muted">{t.summaryOk}</p>
      ) : (
        <ul className="grid list-disc gap-1 pl-5 text-sm">
          {active.map(([message, list]) => (
            <li key={message}>{message.replace("{liste}", list.join(", "))}</li>
          ))}
        </ul>
      )}
      <div className="print:hidden">
        <DocumentSlot typeDocument="PLAN_ACTIONS" objetId={missionId} missionId={missionId} />
      </div>
    </section>
  );
}
