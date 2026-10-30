import { Link } from "react-router-dom";
import type { components } from "@/api/schema";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";
import { DashSection } from "./DashParts";

const t = fr.tableauxDirection;
type Queue = components["schemas"]["FileDecisions"];

const ROWS: { key: keyof Queue; label: string; to: string }[] = [
  { key: "a_cloturer", label: t.queueToClose, to: "/recommandations?vue=actions&statut=VERIFIEE" },
  {
    key: "abandons_proposes",
    label: t.queueAbandons,
    to: "/recommandations?vue=actions&statut=ABANDON_PROPOSE",
  },
  {
    key: "reports_en_attente",
    label: t.queueExtensions,
    to: "/recommandations?vue=actions&report=EN_ATTENTE",
  },
  { key: "missions_a_cloturer", label: t.queueMissionsToClose, to: "/missions?statut=EN_SUIVI" },
  {
    key: "relances_en_echec",
    label: t.queueRemindersFailed,
    to: "/recommandations?vue=actions&relance=ECHEC",
  },
  {
    key: "relances_sans_adresse",
    label: t.queueRemindersNoAddress,
    to: "/recommandations?vue=actions&relance=SANS_ADRESSE",
  },
];

/** File de décisions du RAI : chaque ligne mène à la liste filtrée correspondante. */
export function DecisionQueue({ queue }: { queue: Queue }) {
  const pending = ROWS.some((r) => queue[r.key] > 0);
  return (
    <DashSection title={t.decisionQueue}>
      {!pending && <p className="mb-2 text-sm text-text-muted">{t.decisionQueueEmpty}</p>}
      <ul className="m-0 list-none p-0">
        {ROWS.map((r) => (
          <li key={r.key} className="border-b border-border last:border-b-0">
            <Link
              to={r.to}
              className="flex items-center justify-between gap-3 rounded-md px-1 py-2 text-sm hover:bg-surface-subtle"
            >
              <span>{r.label}</span>
              <span
                className={cn(
                  "font-semibold tabular-nums",
                  queue[r.key] === 0 && "text-text-muted",
                )}
              >
                {queue[r.key].toLocaleString("fr-FR")}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </DashSection>
  );
}
