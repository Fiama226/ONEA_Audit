import { AlertTriangle } from "lucide-react";
import { fr } from "@/i18n/fr";

type Props = {
  /** Date au format AAAA-MM-JJ. */
  echeance: string | null | undefined;
  /** `en_retard` fourni par le serveur (statut relançable et échéance dépassée). */
  enRetard?: boolean;
  /** `jours_retard` fourni par le serveur. */
  joursRetard?: number | null;
};

/**
 * Échéance d'une action : « 12/11/2026 · en retard de 3 j ». Le retard est dit en texte, avec une
 * icône d'alerte et la couleur de danger : jamais la couleur seule.
 */
export function DueDateCell({ echeance, enRetard = false, joursRetard }: Props) {
  if (!echeance) return <span className="text-text-muted">{fr.suivi.dueNone}</span>;
  const [y = "", m = "", d = ""] = echeance.split("-");
  const late = enRetard ? fr.suivi.dueLate.replace("{n}", String(joursRetard ?? 0)) : null;
  return (
    <span className="inline-flex flex-wrap items-center gap-x-1.5">
      <time dateTime={echeance}>{`${d}/${m}/${y}`}</time>
      {late !== null && (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-destructive">
          <span aria-hidden>·</span>
          <AlertTriangle className="size-3.5" aria-label={fr.suivi.dueLateIcon} role="img" />
          {late}
        </span>
      )}
    </span>
  );
}
