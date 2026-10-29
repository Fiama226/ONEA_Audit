import { fr } from "@/i18n/fr";

/** Fiche de suivi de la mission : squelette, rempli par la tâche T9. */
export function TrackingPage() {
  return (
    <section aria-labelledby="tracking-title">
      <h2 id="tracking-title" className="mb-2 text-lg font-semibold">
        {fr.missions.tabTracking}
      </h2>
      <p className="text-sm text-text-muted">{fr.missions.pageSoon}</p>
    </section>
  );
}
