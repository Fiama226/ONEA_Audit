import { Link } from "react-router-dom";
import type { components } from "@/api/schema";
import { DueDateCell } from "@/features/suivi/components/DueDateCell";
import { fr } from "@/i18n/fr";
import { STATUT_MISSION_LABELS } from "@/features/missions/labels";
import type { StatutMission } from "@/features/missions/types";
import { CELL, DashSection, DashTable, ROW } from "./DashParts";

const t = fr.tableauxDirection;
type Late = components["schemas"]["MissionEnRetard"];

export function LateMissionsTable({ missions }: { missions: Late[] }) {
  return (
    <DashSection title={t.lateMissions}>
      <DashTable
        caption={t.lateMissions}
        isEmpty={missions.length === 0}
        empty={t.lateMissionsEmpty}
        columns={[
          { label: t.colReference },
          { label: t.colTitle },
          { label: t.colStatus },
          { label: t.colDueDate },
        ]}
      >
        {missions.map((m) => (
          <tr key={m.mission_id} className={ROW}>
            <td className={CELL}>
              <Link to={`/missions/${m.mission_id}`} className="font-medium underline">
                {m.reference || m.titre}
              </Link>
            </td>
            <td className={CELL}>{m.titre}</td>
            <td className={CELL}>{STATUT_MISSION_LABELS[m.statut as StatutMission] ?? m.statut}</td>
            <td className={CELL}>
              <DueDateCell echeance={m.date_fin_prevue} enRetard joursRetard={m.jours_retard} />
            </td>
          </tr>
        ))}
      </DashTable>
    </DashSection>
  );
}
