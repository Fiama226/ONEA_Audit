import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import type { ActionSuivie } from "../types";
import { DueDateCell } from "./DueDateCell";
import { PriorityBadge } from "./PriorityBadge";
import { SuiviStatusBadge } from "./SuiviStatusBadge";

const t = fr.suiviRegistre;

type Props = {
  action: ActionSuivie;
  onChangeResponsible?: () => void;
};

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-0.5">
      <dt className="text-xs font-medium text-text-muted">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

/** Synthèse d'une action : mission, constat, recommandation, indicateur, échéances et statut. */
export function ActionHeader({ action, onChangeResponsible }: Props) {
  return (
    <section aria-labelledby="action-header-title" className="rounded-lg border border-border p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <h2 id="action-header-title" className="text-lg font-semibold">
          {action.action_libelle}
        </h2>
        <SuiviStatusBadge statut={action.statut} />
      </div>
      <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
        <Item label={t.headerMission}>
          <Link
            to={`/missions/${action.mission.id}/suivi-recommandations`}
            className="text-primary underline-offset-2 hover:underline"
          >
            {action.mission.reference} · {action.mission.titre}
          </Link>
        </Item>
        <Item label={t.headerFinding}>
          {action.constat.reference} · {action.constat.titre}
        </Item>
        <Item label={t.headerRecommendation}>
          <span className="flex flex-wrap items-center gap-2">
            {action.recommandation.libelle}
            <PriorityBadge priorite={action.recommandation.priorite} />
          </span>
        </Item>
        <Item label={t.headerIndicator}>{action.indicateur || fr.suivi.dueNone}</Item>
        <Item label={t.headerResponsible}>
          <span className="flex flex-wrap items-center gap-2">
            {action.responsable.nom_complet}
            {onChangeResponsible && (
              <Button type="button" variant="outline" size="xs" onClick={onChangeResponsible}>
                {t.changeResponsible}
              </Button>
            )}
          </span>
        </Item>
        <Item label={t.headerInitialDue}>
          <DueDateCell echeance={action.echeance_initiale} />
        </Item>
        <Item label={t.headerCurrentDue}>
          <DueDateCell
            echeance={action.echeance}
            enRetard={action.en_retard}
            joursRetard={action.jours_retard}
          />
        </Item>
        <Item label={t.headerExtensions}>{action.nombre_reports}</Item>
        {action.motif_dernier_rejet && (
          <Item label={t.headerRejectionReason}>{action.motif_dernier_rejet}</Item>
        )}
        {action.justification_abandon && (
          <Item label={t.headerAbandonReason}>{action.justification_abandon}</Item>
        )}
      </dl>
    </section>
  );
}
