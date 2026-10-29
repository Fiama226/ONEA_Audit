import { EmptyState } from "@/components/EmptyState";
import { fr } from "@/i18n/fr";

/** Liste des missions : squelette, rempli par la tâche T7. */
export function MissionListPage() {
  return (
    <>
      <h1 className="mb-4 text-2xl font-semibold tracking-[-0.012em]">{fr.missions.title}</h1>
      <EmptyState
        title={fr.missions.emptyTitle}
        description={fr.missions.pageSoon}
        illustration={false}
      />
    </>
  );
}
