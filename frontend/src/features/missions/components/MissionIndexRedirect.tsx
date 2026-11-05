import { Navigate, useParams } from "react-router-dom";
import { useRole } from "@/auth/useRole";
import { fr } from "@/i18n/fr";
import { useMission } from "../api";

/** Page d'arrivée d'une mission : audités et lecteurs sans accès aux travaux vont aux réunions. */
export function MissionIndexRedirect() {
  const { id } = useParams();
  const { is } = useRole();
  const mission = useMission(id);
  if (!mission.data) {
    return mission.isError ? null : (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  if (is("AUDITE") || !mission.data.mes_droits.voir_travaux) {
    return <Navigate to="reunions" replace />;
  }
  return <Navigate to={`etapes/${mission.data.etape_courante?.numero ?? 1}`} replace />;
}
