import { MoreHorizontal } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { PHASE_LABELS } from "../labels";
import type { DroitsMission, Mission } from "../types";
import { MissionStatusBadge } from "./MissionStatusBadge";

export type MissionHeaderAction =
  "plan" | "launch" | "issue-order" | "suspend" | "resume" | "cancel" | "delete";

type ActionDef = { right: keyof DroitsMission; label: string } & (
  { kind: "link" } | { kind: "action"; action: MissionHeaderAction }
);

/** Ordre d'affichage ; chaque entrée n'apparaît que si le serveur accorde le droit correspondant. */
const ACTIONS: ActionDef[] = [
  { right: "modifier", label: "Modifier la mission", kind: "link" },
  { right: "planifier", label: "Planifier la mission", kind: "action", action: "plan" },
  { right: "lancer", label: "Lancer la mission", kind: "action", action: "launch" },
  {
    right: "emettre_ordre",
    label: "Émettre l'ordre de mission",
    kind: "action",
    action: "issue-order",
  },
  { right: "suspendre", label: "Suspendre la mission", kind: "action", action: "suspend" },
  { right: "reprendre", label: "Reprendre la mission", kind: "action", action: "resume" },
  { right: "annuler", label: "Annuler la mission", kind: "action", action: "cancel" },
  { right: "supprimer", label: "Supprimer la mission", kind: "action", action: "delete" },
];

type Props = {
  mission: Mission;
  /** Branché par les écrans de pilotage ; le serveur reste seul juge de l'autorisation. */
  onAction?: (action: MissionHeaderAction) => void;
};

function dates(mission: Mission): string {
  const { date_debut_prevue: start, date_fin_prevue: end } = mission;
  if (!start || !end) return fr.missions.noDates;
  return fr.missions.plannedDates
    .replace("{start}", formatDate(start))
    .replace("{end}", formatDate(end));
}

/** En-tête d'une mission. Les actions viennent uniquement de `mes_droits` (jamais recalculées). */
export function MissionHeader({ mission, onAction }: Props) {
  const available = ACTIONS.filter((a) => mission.mes_droits[a.right]);
  const members = mission.equipe.filter((a) => a.role_mission !== "CHEF_MISSION");

  return (
    <header className="mb-6 grid gap-3">
      {mission.mes_droits.confirmer_ma_declaration && (
        <p
          role="status"
          className="rounded-md border border-warning/50 bg-surface-subtle p-3 text-sm"
        >
          {fr.missions.declarationBanner}
        </p>
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
          {available.length > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button type="button" variant="outline" size="sm">
                  <MoreHorizontal aria-hidden />
                  {fr.missions.actionsMenu}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {available.map((a, i) => {
                  const destructive = a.kind === "action" && a.action === "delete";
                  return (
                    <div key={a.right}>
                      {destructive && i > 0 && <DropdownMenuSeparator />}
                      {a.kind === "link" ? (
                        <DropdownMenuItem asChild>
                          <Link to={`/missions/${mission.id}/modifier`}>{a.label}</Link>
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem
                          variant={destructive ? "destructive" : "default"}
                          onSelect={() => onAction?.(a.action)}
                        >
                          {a.label}
                        </DropdownMenuItem>
                      )}
                    </div>
                  );
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
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
