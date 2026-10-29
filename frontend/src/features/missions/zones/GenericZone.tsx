import { fr } from "@/i18n/fr";
import type { Etape, Mission } from "../types";

/** Zone de travail par défaut d'une étape (squelette ; les zones spécifiques arrivent ensuite). */
export function GenericZone({ step }: { mission: Mission; step: Etape }) {
  return (
    <section aria-labelledby={`zone-${step.id}`} className="rounded-md border border-border p-4">
      <h2 id={`zone-${step.id}`} className="mb-1 text-base font-semibold">
        {step.romain} · {step.titre}
      </h2>
      {step.objectif && <p className="text-sm">{step.objectif}</p>}
      <p className="mt-2 text-sm text-text-muted">{fr.missions.zoneSoon}</p>
    </section>
  );
}
