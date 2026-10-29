import { createElement } from "react";
import { useParams } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { useMission, useSteps } from "../api";
import { MissionStepper } from "../components/MissionStepper";
import { ZONES } from "../zones";
import { GenericZone } from "../zones/GenericZone";

/** Page d'une étape : navigation entre les 18 étapes et zone de travail de l'étape choisie. */
export function StepPage() {
  const { id, numero } = useParams();
  const mission = useMission(id);
  const steps = useSteps(id);
  const selected = Number(numero);

  if (steps.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {fr.missions.stepsLoadError}
      </p>
    );
  }
  if (!mission.data || !steps.data || id === undefined) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const step = steps.data.find((s) => s.numero === selected);
  const zone = ZONES[selected] ?? GenericZone;

  return (
    <div className="grid gap-6 xl:grid-cols-[18rem_minmax(0,1fr)]">
      <nav aria-label={fr.missions.stepperLabel}>
        <MissionStepper steps={steps.data} missionId={id} selected={selected} />
      </nav>
      {step ? (
        createElement(zone, { mission: mission.data, step })
      ) : (
        <p className="text-sm text-text-muted">{fr.errors.notFound}</p>
      )}
    </div>
  );
}
