import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { PHASE_LABELS, STATUT_MISSION_LABELS } from "../labels";
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

function phaseText(mission: Mission): string {
  if (mission.phase) return PHASE_LABELS[mission.phase];
  switch (mission.statut) {
    case "BROUILLON":
    case "PLANIFIEE":
      return fr.missions.phaseNotStarted;
    case "RAPPORT_DIFFUSE":
    case "EN_SUIVI":
    case "CLOTUREE":
      return fr.missions.phaseDone;
    case "SUSPENDUE":
      return STATUT_MISSION_LABELS.SUSPENDUE;
    case "ANNULEE":
      return STATUT_MISSION_LABELS.ANNULEE;
    default:
      return fr.missions.noPhase;
  }
}

/** Prochaine action de la mission : texte, bouton principal (porté par `MissionActions`) ou lien. */
function NextAction({ mission }: { mission: Mission }) {
  const rights = mission.mes_droits;
  const step = mission.etape_courante;
  let text: string | null = null;
  let link: { to: string; label: string } | null = null;
  if (mission.statut === "BROUILLON" && (rights.planifier || rights.modifier)) {
    text = fr.missions.nextDraft;
  } else if (mission.statut === "PLANIFIEE" && rights.lancer) {
    text = fr.missions.nextPlanned;
  } else if (mission.statut === "SUSPENDUE" && rights.reprendre) {
    text = fr.missions.nextSuspended;
  } else if (rights.emettre_ordre && step?.numero === 1) {
    text = fr.missions.nextOrder;
    link = {
      to: `/missions/${mission.id}/etapes/1`,
      label: fr.missionPilotage.actionIssueOrder,
    };
  } else if (step && rights.voir_travaux) {
    text = fr.missions.nextStep.replace("{romain}", step.romain);
    link = {
      to: `/missions/${mission.id}/etapes/${step.numero}`,
      label: fr.missions.nextStepOpen.replace("{romain}", step.romain),
    };
  }
  if (text === null) return null;
  return (
    <div
      role="status"
      aria-label={fr.missions.nextActionLabel}
      className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface-subtle p-3 text-sm print:hidden"
    >
      <p>{text}</p>
      {link && (
        <Button asChild size="sm">
          <Link to={link.to}>{link.label}</Link>
        </Button>
      )}
    </div>
  );
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
      <NextAction mission={mission} />
      <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-text-muted">{fr.missions.phase}</dt>
          <dd>{phaseText(mission)}</dd>
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
