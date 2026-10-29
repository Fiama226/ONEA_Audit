import { Navigate, useParams, type RouteObject } from "react-router-dom";
import { AuditFrameworkPage } from "@/features/analyse/pages/AuditFrameworkPage";
import { useRole } from "@/auth/useRole";
import { fr } from "@/i18n/fr";
import { useMission } from "./api";
import { MissionLayout } from "./components/MissionLayout";
import { InterviewsPage } from "./pages/InterviewsPage";
import { MeetingsPage } from "./pages/MeetingsPage";
import { MissionFormPage } from "./pages/MissionFormPage";
import { MissionListPage } from "./pages/MissionListPage";
import { StepPage } from "./pages/StepPage";
import { TeamPage } from "./pages/TeamPage";
import { TrackingPage } from "./pages/TrackingPage";

/** Page d'arrivée d'une mission : audités et lecteurs sans accès aux travaux vont aux réunions. */
function MissionIndexRedirect() {
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

/** Routes enfants de `/missions` (la garde de rôle est posée dans routes.tsx). */
export const missionRoutes: RouteObject[] = [
  { index: true, element: <MissionListPage /> },
  { path: "nouvelle", element: <MissionFormPage /> },
  {
    path: ":id",
    element: <MissionLayout />,
    children: [
      { index: true, element: <MissionIndexRedirect /> },
      { path: "modifier", element: <MissionFormPage /> },
      { path: "etapes/:numero", element: <StepPage /> },
      { path: "equipe", element: <TeamPage /> },
      { path: "reunions", element: <MeetingsPage /> },
      { path: "entretiens", element: <InterviewsPage /> },
      { path: "suivi", element: <TrackingPage /> },
      { path: "referentiel-audit", element: <AuditFrameworkPage /> },
    ],
  },
];
