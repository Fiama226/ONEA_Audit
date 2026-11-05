import type { RouteObject } from "react-router-dom";
import { lazyRoute } from "@/components/lazyRoute";

const load = {
  // La redirection d'arrivée lit la mission (api.ts) : chargée à la demande, hors du JS d'entrée.
  indexRedirect: () => import("./components/MissionIndexRedirect"),
  layout: () => import("./components/MissionLayout"),
  list: () => import("./pages/MissionListPage"),
  form: () => import("./pages/MissionFormPage"),
  step: () => import("./pages/StepPage"),
  team: () => import("./pages/TeamPage"),
  meetings: () => import("./pages/MeetingsPage"),
  interviews: () => import("./pages/InterviewsPage"),
  tracking: () => import("./pages/TrackingPage"),
  framework: () => import("@/features/analyse/pages/AuditFrameworkPage"),
  fiche: () => import("@/features/accomplissement/pages/FichePage"),
  constats: () => import("@/features/constats/pages/ConstatsAuditePage"),
  constat: () => import("@/features/constats/pages/ConstatPage"),
  rapport: () => import("@/features/communication/pages/RapportPage"),
  reponses: () => import("@/features/communication/pages/ReponsesProvisoirePage"),
  plan: () => import("@/features/recommandations/pages/PlanActionsPage"),
  followUp: () => import("@/features/suivi/pages/MissionFollowUpPage"),
};

/** Routes enfants de `/missions` (la garde de rôle est posée dans routes.tsx). */
export const missionRoutes: RouteObject[] = [
  { index: true, element: lazyRoute(load.list, "MissionListPage") },
  { path: "nouvelle", element: lazyRoute(load.form, "MissionFormPage") },
  {
    path: ":id",
    element: lazyRoute(load.layout, "MissionLayout"),
    children: [
      { index: true, element: lazyRoute(load.indexRedirect, "MissionIndexRedirect") },
      { path: "modifier", element: lazyRoute(load.form, "MissionFormPage") },
      { path: "etapes/:numero", element: lazyRoute(load.step, "StepPage") },
      { path: "equipe", element: lazyRoute(load.team, "TeamPage") },
      { path: "reunions", element: lazyRoute(load.meetings, "MeetingsPage") },
      { path: "entretiens", element: lazyRoute(load.interviews, "InterviewsPage") },
      { path: "suivi", element: lazyRoute(load.tracking, "TrackingPage") },
      { path: "referentiel-audit", element: lazyRoute(load.framework, "AuditFrameworkPage") },
      { path: "fiches/:ficheId", element: lazyRoute(load.fiche, "FichePage") },
      { path: "constats", element: lazyRoute(load.constats, "ConstatsAuditePage") },
      { path: "constats/:constatId", element: lazyRoute(load.constat, "ConstatPage") },
      { path: "rapport", element: lazyRoute(load.rapport, "RapportPage") },
      { path: "reponses-rapport", element: lazyRoute(load.reponses, "ReponsesProvisoirePage") },
      { path: "plan-actions", element: lazyRoute(load.plan, "PlanActionsPage") },
      {
        path: "suivi-recommandations",
        element: lazyRoute(load.followUp, "MissionFollowUpPage"),
      },
    ],
  },
];
