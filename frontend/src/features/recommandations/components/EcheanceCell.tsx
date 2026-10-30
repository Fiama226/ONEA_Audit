import { fr } from "@/i18n/fr";
import { STATUTS_ACTION_CLOS } from "../labels";
import type { StatutAction } from "../types";

type Props = {
  /** Date au format AAAA-MM-JJ. */
  echeance: string | null | undefined;
  statut: StatutAction;
  /** Date du jour (AAAA-MM-JJ), injectable pour les tests ; l'heure d'Ouagadougou est UTC. */
  today?: string;
};

/** Échéance d'une action : « JJ/MM/AAAA », avec la mention « En retard » si elle est dépassée. */
export function EcheanceCell({
  echeance,
  statut,
  today = new Date().toISOString().slice(0, 10),
}: Props) {
  if (!echeance) return <span className="text-text-muted">{fr.communication.dueNone}</span>;
  const [y = "", m = "", d = ""] = echeance.split("-");
  const late = echeance < today && !STATUTS_ACTION_CLOS.includes(statut);
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <time dateTime={echeance}>{`${d}/${m}/${y}`}</time>
      {late && (
        <span className="text-xs font-medium text-destructive">{fr.communication.dueLate}</span>
      )}
    </span>
  );
}
