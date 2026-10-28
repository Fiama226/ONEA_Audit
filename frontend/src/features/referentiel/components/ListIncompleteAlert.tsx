import { fr } from "@/i18n/fr";
import { ALERT_CLASS } from "./FormField";

/** Alerte visible si le serveur annonce plus d'éléments que ceux chargés. */
export function ListIncompleteAlert({ count, loaded }: { count: number; loaded: number }) {
  if (count <= loaded) return null;
  return (
    <p role="alert" className={ALERT_CLASS}>
      {fr.refStructure.listIncomplete
        .replace("{loaded}", String(loaded))
        .replace("{count}", String(count))}
    </p>
  );
}
