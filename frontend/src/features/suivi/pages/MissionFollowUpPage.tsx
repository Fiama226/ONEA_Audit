import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/auth/useAuth";
import { fr } from "@/i18n/fr";
import { useFollowUpActions, useFollowUpRecommendations, useMissionsToClose } from "../api";
import { CloseMissionDialog } from "../components/CloseMissionDialog";
import { DueDateCell } from "../components/DueDateCell";
import { PriorityBadge } from "../components/PriorityBadge";
import { SuiviStatusBadge } from "../components/SuiviStatusBadge";
import { STATUT_RECOMMANDATION_SUIVI_LABELS, STATUTS_SUIVI_CLOS } from "../labels";
import type { ActionSuivie } from "../types";

const t = fr.suiviRegistre;

type CloseProps = { missionId: string; openActions: number; missionClosed: boolean };

/** Bouton « Clôturer la mission » (RAI) : actif seulement si le serveur la déclare à clôturer. */
function CloseSection({ missionId, openActions, missionClosed }: CloseProps) {
  const toClose = useMissionsToClose();
  const [open, setOpen] = useState(false);

  if (missionClosed) return <p className="text-sm text-text-muted">{t.missionClosed}</p>;
  if (toClose.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.missionClosableLoadError}
      </p>
    );
  }
  const closable = toClose.data?.results.some((m) => m.id === missionId) ?? false;
  const explanation = toClose.isLoading
    ? null
    : closable
      ? null
      : openActions > 0
        ? t.missionOpenActions.replace("{n}", String(openActions))
        : t.missionNotClosable;

  return (
    <div className="flex flex-wrap items-center gap-3 print:hidden">
      <Button
        type="button"
        disabled={!closable}
        aria-describedby={explanation ? "mission-close-help" : undefined}
        onClick={() => setOpen(true)}
      >
        {t.missionClose}
      </Button>
      {explanation && (
        <p id="mission-close-help" className="text-sm text-text-muted">
          {explanation}
        </p>
      )}
      <CloseMissionDialog missionId={missionId} open={open} onOpenChange={setOpen} />
    </div>
  );
}

function ActionRows({ actions }: { actions: ActionSuivie[] }) {
  return (
    <ul className="divide-y divide-border">
      {actions.map((a) => (
        <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 py-2 text-sm">
          <Link
            to={`/recommandations/actions/${a.id}`}
            className="font-medium text-primary underline-offset-2 hover:underline"
          >
            {a.action_libelle}
          </Link>
          <span className="flex flex-wrap items-center gap-4">
            <span className="text-text-muted">{a.responsable.nom_complet}</span>
            <DueDateCell
              echeance={a.echeance}
              enRetard={a.en_retard}
              joursRetard={a.jours_retard}
            />
            <SuiviStatusBadge statut={a.statut} />
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Suivi des recommandations d'une mission : actions groupées par recommandation. */
export function MissionFollowUpPage() {
  const { id } = useParams();
  const { me } = useAuth();
  const actions = useFollowUpActions({ mission: id });
  const recommendations = useFollowUpRecommendations({ mission: id });

  const failed =
    (actions.isError && !actions.data) || (recommendations.isError && !recommendations.data);
  const loading = actions.isLoading || recommendations.isLoading;
  const actionList = actions.data?.results ?? [];
  const recoList = recommendations.data?.results ?? [];

  // Toute recommandation de la mission, avec ou sans action ; les actions d'une recommandation
  // inconnue de la liste (cas limite) restent affichées sous un en-tête reconstitué.
  const groups = recoList.map((r) => ({
    key: r.id,
    libelle: r.libelle,
    priorite: r.priorite,
    statut: STATUT_RECOMMANDATION_SUIVI_LABELS[r.statut_suivi],
    actions: actionList.filter((a) => a.recommandation.id === r.id),
  }));
  for (const a of actionList) {
    if (!groups.some((g) => g.key === a.recommandation.id)) {
      groups.push({
        key: a.recommandation.id,
        libelle: a.recommandation.libelle,
        priorite: a.recommandation.priorite,
        statut: "",
        actions: actionList.filter((x) => x.recommandation.id === a.recommandation.id),
      });
    }
  }

  const openActions = actionList.filter((a) => !STATUTS_SUIVI_CLOS.includes(a.statut)).length;
  const missionClosed =
    actionList.length > 0 && actionList.every((a) => a.mission.statut === "CLOTUREE");

  return (
    <>
      <h2 className="mb-6 text-2xl font-semibold tracking-[-0.012em]">
        {fr.suivi.missionFollowUpTitle}
      </h2>
      {failed ? (
        <p role="alert" className={ALERT_CLASS}>
          {t.missionLoadError}
        </p>
      ) : loading ? (
        <p role="status" className="text-sm text-text-muted">
          {fr.common.loading}
        </p>
      ) : (
        <div className="grid gap-5">
          {me?.role === "RAI" && id && (
            <CloseSection missionId={id} openActions={openActions} missionClosed={missionClosed} />
          )}
          {groups.length === 0 ? (
            <p className="text-sm text-text-muted">{t.missionEmpty}</p>
          ) : (
            groups.map((g) => (
              <article
                key={g.key}
                aria-labelledby={`reco-${g.key}`}
                className="rounded-lg border border-border p-4"
              >
                <header className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <h3 id={`reco-${g.key}`} className="text-base font-semibold">
                    {g.libelle}
                  </h3>
                  <span className="flex items-center gap-3 text-sm">
                    <PriorityBadge priorite={g.priorite} />
                    {g.statut && <span>{g.statut}</span>}
                  </span>
                </header>
                {g.actions.length === 0 ? (
                  <p className="text-sm text-text-muted">{t.missionRecommendationNoAction}</p>
                ) : (
                  <ActionRows actions={g.actions} />
                )}
              </article>
            ))
          )}
        </div>
      )}
    </>
  );
}
