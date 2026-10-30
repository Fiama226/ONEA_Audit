import { fr } from "@/i18n/fr";

/** Constats soumis à l'audité (squelette : liste et réponse livrées par une tâche suivante du lot 6). */
export function ConstatsAuditePage() {
  return (
    <section aria-labelledby="constats-audite-title" className="grid gap-2">
      <h2 id="constats-audite-title" className="text-lg font-semibold">
        {fr.missions.tabConstats}
      </h2>
      <p className="text-sm text-text-muted">{fr.accomplissement.zoneSoon}</p>
    </section>
  );
}
