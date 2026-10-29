import { fr } from "@/i18n/fr";

/** Équipe de la mission : squelette, rempli par la tâche T7. */
export function TeamPage() {
  return (
    <section aria-labelledby="team-title">
      <h2 id="team-title" className="mb-2 text-lg font-semibold">
        {fr.missions.tabTeam}
      </h2>
      <p className="text-sm text-text-muted">{fr.missions.pageSoon}</p>
    </section>
  );
}
