import { useParams } from "react-router-dom";
import { fr } from "@/i18n/fr";

/** Création et modification d'une mission : squelette, rempli par la tâche T7. */
export function MissionFormPage() {
  const { id } = useParams();
  return (
    <>
      <h1 className="mb-4 text-2xl font-semibold tracking-[-0.012em]">
        {id ? fr.missions.editMission : fr.missions.newMission}
      </h1>
      <p className="text-sm text-text-muted">{fr.missions.pageSoon}</p>
    </>
  );
}
