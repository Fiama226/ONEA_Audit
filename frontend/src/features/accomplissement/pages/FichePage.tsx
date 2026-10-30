import { useParams } from "react-router-dom";
import { fr } from "@/i18n/fr";

/** Fiche de test (squelette : le contenu est livré par une tâche suivante du lot 6). */
export function FichePage() {
  const { ficheId } = useParams();
  return (
    <section aria-labelledby="FichePage-title" className="grid gap-2">
      <h2 id="FichePage-title" className="text-lg font-semibold">
        Fiche de test
      </h2>
      <p className="text-sm text-text-muted" data-id={ficheId}>
        {fr.accomplissement.zoneSoon}
      </p>
    </section>
  );
}
