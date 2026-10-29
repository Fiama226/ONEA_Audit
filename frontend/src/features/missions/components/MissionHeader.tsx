import { useState } from "react";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { PHASE_LABELS } from "../labels";
import type { Mission } from "../types";
import { DeclarationDialog } from "./DeclarationDialog";
import { MissionActions } from "./MissionActions";
import { MissionStatusBadge } from "./MissionStatusBadge";

function dates(mission: Mission): string {
  const { date_debut_prevue: start, date_fin_prevue: end } = mission;
  if (!start || !end) return fr.missions.noDates;
  return fr.missions.plannedDates
    .replace("{start}", formatDate(start))
    .replace("{end}", formatDate(end));
}

/** En-tête d'une mission. Les actions viennent uniquement de `mes_droits` (jamais recalculées). */
export function MissionHeader({ mission }: { mission: Mission }) {
  const [declaring, setDeclaring] = useState(false);
  const members = mission.equipe.filter((a) => a.role_mission !== "CHEF_MISSION");

  return (
    <header className="mb-6 grid gap-3">
      {mission.mes_droits.confirmer_ma_declaration && (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-warning/50 bg-surface-subtle p-3 text-sm print:hidden"
        >
          <p>{fr.missions.declarationBanner}</p>
          <Button type="button" size="sm" onClick={() => setDeclaring(true)}>
            {fr.missionPilotage.confirmMyDeclaration}
          </Button>
        </div>
      )}
      {declaring && (
        <DeclarationDialog missionId={mission.id} onClose={() => setDeclaring(false)} />
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-text-muted">
            {mission.reference || fr.missions.draft}
          </p>
          <h1 className="text-2xl font-semibold tracking-[-0.012em]">{mission.titre}</h1>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <MissionStatusBadge statut={mission.statut} />
          <MissionActions mission={mission} />
        </div>
      </div>
      <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-text-muted">{fr.missions.phase}</dt>
          <dd>{mission.phase ? PHASE_LABELS[mission.phase] : fr.missions.noPhase}</dd>
        </div>
        <div>
          <dt className="text-text-muted">{fr.missions.colDates}</dt>
          <dd>{dates(mission)}</dd>
        </div>
        <div>
          <dt className="text-text-muted">{fr.missions.chief}</dt>
          <dd>{mission.chef_mission?.nom_complet ?? fr.missions.noChief}</dd>
        </div>
        <div>
          <dt className="text-text-muted">{fr.missions.team}</dt>
          <dd>
            {members.length > 0
              ? members.map((m) => m.utilisateur_detail.nom_complet).join(", ")
              : fr.missions.noTeam}
          </dd>
        </div>
      </dl>
    </header>
  );
}
