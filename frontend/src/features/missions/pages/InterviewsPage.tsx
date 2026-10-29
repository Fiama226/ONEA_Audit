import { fr } from "@/i18n/fr";

/** Entretiens de la mission : squelette, rempli par la tâche T9. */
export function InterviewsPage() {
  return (
    <section aria-labelledby="interviews-title">
      <h2 id="interviews-title" className="mb-2 text-lg font-semibold">
        {fr.missions.tabInterviews}
      </h2>
      <p className="text-sm text-text-muted">{fr.missions.pageSoon}</p>
    </section>
  );
}
