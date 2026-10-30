import { useParams } from "react-router-dom";
import { fr } from "@/i18n/fr";

/** Constat (squelette : le contenu est livré par une tâche suivante du lot 6). */
export function ConstatPage() {
  const { constatId } = useParams();
  return (
    <section aria-labelledby="ConstatPage-title" className="grid gap-2">
      <h2 id="ConstatPage-title" className="text-lg font-semibold">
        Constat
      </h2>
      <p className="text-sm text-text-muted" data-id={constatId}>
        {fr.accomplissement.zoneSoon}
      </p>
    </section>
  );
}
