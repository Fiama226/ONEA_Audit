import { Navigate, type RouteObject } from "react-router-dom";
import { AuditableObjectsPage } from "./pages/AuditableObjectsPage";
import { DirectionsPage } from "./pages/DirectionsPage";
import { ProcessFormPage } from "./pages/ProcessFormPage";
import { ProcessListPage } from "./pages/ProcessListPage";
import { RiskFormPage } from "./pages/RiskFormPage";
import { RiskMapComparePage } from "./pages/RiskMapComparePage";
import { RiskMapDetailPage } from "./pages/RiskMapDetailPage";
import { RiskMapListPage } from "./pages/RiskMapListPage";

/** Routes enfants de `/referentiel` (la garde de rôle et le layout sont posés dans routes.tsx). */
export const referentielRoutes: RouteObject[] = [
  { index: true, element: <Navigate to="cartographies" replace /> },
  { path: "cartographies", element: <RiskMapListPage /> },
  { path: "cartographies/:id", element: <RiskMapDetailPage /> },
  { path: "cartographies/:id/comparer", element: <RiskMapComparePage /> },
  { path: "risques/nouveau", element: <RiskFormPage /> },
  { path: "risques/:id", element: <RiskFormPage /> },
  { path: "processus", element: <ProcessListPage /> },
  { path: "processus/nouveau", element: <ProcessFormPage /> },
  { path: "processus/:id", element: <ProcessFormPage /> },
  { path: "directions", element: <DirectionsPage /> },
  { path: "objets-auditables", element: <AuditableObjectsPage /> },
];
