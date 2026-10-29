import { Lock } from "lucide-react";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import type { AuditPlan } from "../types";

/** Bandeau d'un programme validé (figé, lecture seule). */
export function PlanFrozenBanner({ plan }: { plan: AuditPlan }) {
  const p = fr.programmation;
  const date = plan.valide_le ? ` ${formatDate(plan.valide_le)}` : "";
  const by = plan.valide_par ? ` ${p.frozenBy} ${plan.valide_par.nom_complet}` : "";
  return (
    <p
      role="status"
      className="flex items-center gap-2 rounded-md border border-border bg-surface-subtle px-4 py-3 text-sm"
    >
      <Lock className="size-4 shrink-0" aria-hidden />
      <span>{`${p.frozenOn}${date}${by} : ${p.frozenSuffix}`}</span>
    </p>
  );
}
