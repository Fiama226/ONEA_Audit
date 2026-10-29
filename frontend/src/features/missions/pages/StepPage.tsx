import { createElement } from "react";
import { useParams } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { useMission, useSteps } from "../api";
import { MissionStepper } from "../components/MissionStepper";
import { StepActions } from "../components/StepActions";
import { StepJournal } from "../components/StepJournal";
import { StepPlanningForm } from "../components/StepPlanningForm";
import { StepStatusBadge } from "../components/StepStatusBadge";
import { PHASE_LABELS } from "../labels";
import type { Etape } from "../types";
import { ZONES } from "../zones";
import { GenericZone } from "../zones/GenericZone";

const m = fr.missionEtapes;

function StepHeader({ step }: { step: Etape }) {
  const missing = step.livrables_manquants;
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <h2 className="text-xl font-semibold">
          {m.stepTitle.replace("{romain}", step.romain).replace("{titre}", step.titre)}
        </h2>
        <StepStatusBadge statut={step.statut} />
      </div>
      <p className="text-sm text-text-muted">
        {m.phaseLine.replace("{phase}", PHASE_LABELS[step.phase])}
        {step.jalon && <> · {m.milestone}</>}
      </p>
      {step.objectif && (
        <p className="text-sm">
          <span className="font-medium">{m.objective} : </span>
          {step.objectif}
        </p>
      )}
      <section aria-labelledby={`deliverables-${step.id}`} className="grid gap-1">
        <h3 id={`deliverables-${step.id}`} className="text-base font-semibold">
          {m.deliverables}
        </h3>
        {step.livrables.length === 0 ? (
          <p className="text-sm text-text-muted">{m.noDeliverables}</p>
        ) : (
          <ul className="list-disc pl-5 text-sm">
            {step.livrables.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        )}
        {missing.length > 0 && (
          <ul className="text-sm text-destructive">
            {missing.map((item) => (
              <li key={item}>{m.missing.replace("{item}", item)}</li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/** Page d'une étape : navigation entre les 18 étapes, en-tête, actions, zone de travail et journal. */
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
      <nav aria-label={fr.missions.stepperLabel} className="print:hidden">
        <MissionStepper steps={steps.data} missionId={id} selected={selected} />
      </nav>
      {step ? (
        <div className="grid min-w-0 content-start gap-6">
          <StepHeader step={step} />
          <StepActions key={step.id} step={step} />
          {step.actions_possibles.includes("PLANIFIER") && (
            <StepPlanningForm key={step.id} step={step} />
          )}
          {createElement(zone, { mission: mission.data, step })}
          <StepJournal step={step} />
        </div>
      ) : (
        <p role="alert" className="text-sm text-text-muted">
          {m.notFound}
        </p>
      )}
    </div>
  );
}
