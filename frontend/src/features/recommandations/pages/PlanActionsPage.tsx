import { Link, useParams } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { useRole } from "@/auth/useRole";
import { ALERT_CLASS } from "@/components/form/FormField";
import { useRecommendations } from "@/features/constats/api";
import { useMission, useSteps } from "@/features/missions/api";
import type { Etape, Mission } from "@/features/missions/types";
import { fr } from "@/i18n/fr";
import { useActions, useActionPlanSummary, useRiskAcceptances } from "../api";
import { CommitmentPanel } from "../components/CommitmentPanel";
import { PlanSummary } from "../components/PlanSummary";
import { RecommendationPlanCard } from "../components/RecommendationPlanCard";

const t = fr.planActions;
const STATUTS_CLOS: readonly string[] = ["TERMINEE", "VALIDEE", "NON_APPLICABLE"];

type ContentProps = { mission: Mission; step: Etape | undefined };

/**
 * Contenu du plan d'actions (page et zone de l'étape XVI) : une carte par recommandation d'un
 * constat validé, engagement et contrôles. Lecture seule dès que l'étape XVI est close.
 */
export function PlanActionsContent({ mission, step }: ContentProps) {
  const { is } = useRole();
  const { me } = useAuth();
  const summary = useActionPlanSummary(mission.id);
  const actions = useActions({ mission: mission.id });
  const acceptances = useRiskAcceptances({ mission: mission.id });
  const recommendations = useRecommendations(mission.id);

  if (summary.isError || actions.isError || acceptances.isError || recommendations.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  }
  if (!summary.data || !actions.data || !acceptances.data || !recommendations.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }

  const audite = is("AUDITE");
  const rai = is("RAI");
  const writable = step !== undefined && !STATUTS_CLOS.includes(step.statut);
  const canPropose = writable && (mission.mes_droits.contribuer || audite);
  const lignes = summary.data.recommandations;

  return (
    <div className="grid gap-4">
      <p className="hidden text-sm font-medium print:block">
        {t.printTitle} · {mission.reference} · {mission.titre}
      </p>
      {!writable && <p className="text-sm text-text-muted">{t.readOnly}</p>}
      {lignes.length === 0 ? (
        <p className="text-sm text-text-muted">{t.empty}</p>
      ) : (
        lignes.map((ligne) => {
          const recommandation = recommendations.data.results.find(
            (r) => `${r.constat_reference}-${r.ordre}` === ligne.reference,
          );
          const acceptation = acceptances.data.results.find((a) => a.id === ligne.acceptation?.id);
          return (
            <RecommendationPlanCard
              key={ligne.reference}
              missionId={mission.id}
              ligne={ligne}
              recommandationId={recommandation?.id}
              actions={actions.data.results.filter((a) => a.recommandation === recommandation?.id)}
              acceptation={acceptation}
              canAdd={canPropose && !ligne.acceptation}
              canAccept={canPropose && audite && !ligne.acceptation && ligne.nb_actions === 0}
              canWithdraw={
                writable &&
                ligne.acceptation !== null &&
                (rai || (audite && ligne.acceptation.auteur === me?.id))
              }
            />
          );
        })
      )}
      <CommitmentPanel
        missionId={mission.id}
        summary={summary.data}
        audite={audite}
        writable={writable}
      />
      <PlanSummary missionId={mission.id} summary={summary.data} />
    </div>
  );
}

/** Plan d'actions de la mission (`/missions/:id/plan-actions`). */
export function PlanActionsPage() {
  const { id } = useParams();
  const mission = useMission(id);
  const steps = useSteps(id);

  if (mission.isError || steps.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  }
  if (!mission.data || !steps.data) {
    return <p role="status">{fr.common.loading}</p>;
  }
  return (
    <section aria-labelledby="plan-actions-title" className="grid gap-4">
      <div className="print:hidden">
        <Link to={`/missions/${mission.data.id}`} className="text-sm text-primary underline">
          {t.back}
        </Link>
      </div>
      <h2 id="plan-actions-title" className="text-lg font-semibold">
        {fr.communication.planActionsTitle}
      </h2>
      <PlanActionsContent mission={mission.data} step={steps.data.find((s) => s.numero === 16)} />
    </section>
  );
}
