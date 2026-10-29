import { Check } from "lucide-react";
import { Link } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";
import { PHASE_LABELS, PHASE_ORDER, PHASE_RANGES } from "../labels";
import type { Etape, Phase } from "../types";
import { StepStatusBadge } from "./StepStatusBadge";

type Props = { steps: Etape[]; missionId: string; selected?: number };

const DONE = new Set(["VALIDEE", "NON_APPLICABLE"]);

/**
 * Une phase est « future » tant que toutes ses étapes sont à faire et qu'une phase précédente
 * n'est pas entièrement terminée : elle reste lisible mais en retrait.
 */
function isFuture(phase: Phase, byPhase: Map<Phase, Etape[]>): boolean {
  const own = byPhase.get(phase) ?? [];
  if (own.some((s) => s.statut !== "A_FAIRE")) return false;
  const index = PHASE_ORDER.indexOf(phase);
  return PHASE_ORDER.slice(0, index).some((p) =>
    (byPhase.get(p) ?? []).some((s) => !DONE.has(s.statut)),
  );
}

/** Les 18 étapes en trois sections (phases) ; chaque étape est un lien vers sa page. */
export function MissionStepper({ steps, missionId, selected }: Props) {
  const byPhase = new Map<Phase, Etape[]>();
  for (const step of [...steps].sort((a, b) => a.numero - b.numero)) {
    byPhase.set(step.phase, [...(byPhase.get(step.phase) ?? []), step]);
  }

  return (
    <div className="grid gap-5">
      {PHASE_ORDER.map((phase) => {
        const items = byPhase.get(phase) ?? [];
        if (items.length === 0) return null;
        const future = isFuture(phase, byPhase);
        const headingId = `phase-${missionId}-${phase}`;
        return (
          <section key={phase} aria-labelledby={headingId}>
            <h2 id={headingId} className="mb-2 text-sm font-semibold">
              {PHASE_LABELS[phase]}{" "}
              <span className="font-normal text-text-muted">
                {fr.missions.stepRange.replace("{range}", PHASE_RANGES[phase])}
              </span>
            </h2>
            <ol className="grid gap-1">
              {items.map((step) => {
                const current = step.numero === selected;
                return (
                  <li key={step.id}>
                    <Link
                      to={`/missions/${missionId}/etapes/${step.numero}`}
                      aria-current={current ? "step" : undefined}
                      className={cn(
                        "flex items-start gap-3 rounded-md border px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-ring",
                        current
                          ? "border-primary bg-surface-subtle"
                          : "border-transparent hover:bg-surface-subtle",
                        future && !current && "text-text-muted",
                      )}
                    >
                      <span className="w-9 shrink-0 font-semibold tabular-nums">
                        {step.romain}
                        {step.statut === "VALIDEE" && (
                          <Check aria-hidden className="ml-1 inline size-3.5 text-success-text" />
                        )}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block">{step.titre}</span>
                        <span className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5">
                          <StepStatusBadge statut={step.statut} />
                          {step.jalon && (
                            <span className="text-xs font-medium text-text-muted">
                              {fr.missions.milestone}
                            </span>
                          )}
                        </span>
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ol>
          </section>
        );
      })}
    </div>
  );
}
