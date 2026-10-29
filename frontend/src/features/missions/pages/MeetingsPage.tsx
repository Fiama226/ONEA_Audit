import { fr } from "@/i18n/fr";

/** Réunions de la mission : squelette, rempli par la tâche T9. */
export function MeetingsPage() {
  return (
    <section aria-labelledby="meetings-title">
      <h2 id="meetings-title" className="mb-2 text-lg font-semibold">
        {fr.missions.tabMeetings}
      </h2>
      <p className="text-sm text-text-muted">{fr.missions.pageSoon}</p>
    </section>
  );
}
