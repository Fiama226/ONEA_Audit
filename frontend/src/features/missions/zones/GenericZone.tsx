import { fr } from "@/i18n/fr";
import type { Etape, Mission } from "../types";

/** Lot qui livre les formulaires de chaque étape sans zone propre (plan du lot 3, D7). */
export const LOT_LIVRABLES: Record<number, number> = {
  3: 5,
  5: 5,
  6: 5,
  7: 5,
  8: 6,
  9: 6,
  10: 6,
  12: 6,
  13: 6,
  14: 6,
  15: 7,
  16: 7,
  17: 7,
  18: 7,
};

/** Zone de travail par défaut d'une étape : annonce le lot qui apportera ses formulaires. */
export function GenericZone({ step }: { mission: Mission; step: Etape }) {
  const lot = LOT_LIVRABLES[step.numero];
  const id = `zone-${step.id}`;
  return (
    <section aria-labelledby={id} className="grid gap-2 rounded-md border border-border p-4">
      <h3 id={id} className="text-base font-semibold">
        {fr.missionEtapes.workTitle}
      </h3>
      {/* Les livrables attendus sont listés par la page d'étape, au-dessus de la zone. */}
      {lot !== undefined && (
        <p className="text-sm text-text-muted">
          {fr.missionEtapes.genericSoon.replace("{lot}", String(lot))}
        </p>
      )}
    </section>
  );
}
