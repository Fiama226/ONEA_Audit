import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { components } from "@/api/schema";
import { fr } from "@/i18n/fr";
import { CELL, DashSection, DashTable, ROW } from "./DashParts";

const t = fr.tableauxDirection;
type Risk = components["schemas"]["RisqueEleve"];

/** Risques élevés : la couverture est dite en texte et par une icône. */
export function HighRisksTable({ risks }: { risks: Risk[] }) {
  return (
    <DashSection title={t.highRisks}>
      <DashTable
        caption={t.highRisks}
        isEmpty={risks.length === 0}
        empty={t.highRisksEmpty}
        columns={[
          { label: t.colCode },
          { label: t.colRisk },
          { label: t.colProcess },
          { label: t.colMissions },
          { label: t.colCoverage },
        ]}
      >
        {risks.map((r) => (
          <tr key={r.id} className={ROW}>
            <td className={CELL}>{r.code}</td>
            <td className={CELL}>{r.libelle}</td>
            <td className={CELL}>{r.processus_code}</td>
            <td className={CELL}>{r.missions.join(", ") || fr.charts.none}</td>
            <td className={CELL}>
              {r.couvert ? (
                <span className="inline-flex items-center gap-1.5">
                  <CheckCircle2 aria-hidden="true" className="size-4 text-success-text" />
                  {t.covered}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 font-medium">
                  <AlertTriangle aria-hidden="true" className="size-4 text-destructive" />
                  {t.notCovered}
                </span>
              )}
            </td>
          </tr>
        ))}
      </DashTable>
    </DashSection>
  );
}
