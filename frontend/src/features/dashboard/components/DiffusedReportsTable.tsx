import type { components } from "@/api/schema";
import { STATUT_MISSION_LABELS } from "@/features/missions/labels";
import type { StatutMission } from "@/features/missions/types";
import { fr } from "@/i18n/fr";
import { CELL, DashSection, DashTable, ROW } from "./DashParts";

const t = fr.tableauxDirection;
type Report = components["schemas"]["RapportDiffuseResume"];

export function DiffusedReportsTable({ reports }: { reports: Report[] }) {
  return (
    <DashSection title={t.diffusedReports}>
      <DashTable
        caption={t.diffusedReports}
        isEmpty={reports.length === 0}
        empty={t.diffusedReportsEmpty}
        columns={[
          { label: t.colReference },
          { label: t.colTitle },
          { label: t.colStatus },
          { label: t.colActions, numeric: true },
        ]}
      >
        {reports.map((r) => (
          <tr key={r.mission_id} className={ROW}>
            <td className={CELL}>{r.reference}</td>
            <td className={CELL}>{r.titre}</td>
            <td className={CELL}>{STATUT_MISSION_LABELS[r.statut as StatutMission] ?? r.statut}</td>
            <td className={`${CELL} text-right tabular-nums`}>
              {t.actionsOf
                .replace("{n}", String(r.actions_cloturees))
                .replace("{total}", String(r.nombre_actions))}
            </td>
          </tr>
        ))}
      </DashTable>
    </DashSection>
  );
}
