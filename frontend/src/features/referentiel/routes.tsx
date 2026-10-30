import { Navigate, useSearchParams, type RouteObject } from "react-router-dom";
import { lazyRoute } from "@/components/lazyRoute";

const load = {
  objects: () => import("./pages/AuditableObjectsPage"),
  directions: () => import("./pages/DirectionsPage"),
  processForm: () => import("./pages/ProcessFormPage"),
  processList: () => import("./pages/ProcessListPage"),
  riskForm: () => import("./pages/RiskFormPage"),
  compare: () => import("./pages/RiskMapComparePage"),
  mapDetail: () => import("./pages/RiskMapDetailPage"),
  mapList: () => import("./pages/RiskMapListPage"),
};

const newRisk = () => lazyRoute(load.riskForm, "RiskFormPage", { creating: true });

/** Compatibilité : l'ancienne adresse `risques/nouveau?cartographie=<id>` renvoie vers la nouvelle. */
function LegacyNewRisk() {
  const [params] = useSearchParams();
  const map = params.get("cartographie");
  if (map) return <Navigate to={`/referentiel/cartographies/${map}/risques/nouveau`} replace />;
  return legacyNewRiskPage;
}
const legacyNewRiskPage = newRisk();

/** Routes enfants de `/referentiel` (la garde de rôle et le layout sont posés dans routes.tsx). */
export const referentielRoutes: RouteObject[] = [
  { index: true, element: <Navigate to="cartographies" replace /> },
  { path: "cartographies", element: lazyRoute(load.mapList, "RiskMapListPage") },
  { path: "cartographies/:id", element: lazyRoute(load.mapDetail, "RiskMapDetailPage") },
  { path: "cartographies/:id/comparer", element: lazyRoute(load.compare, "RiskMapComparePage") },
  { path: "cartographies/:id/risques/nouveau", element: newRisk() },
  { path: "risques/nouveau", element: <LegacyNewRisk /> },
  { path: "risques/:id", element: lazyRoute(load.riskForm, "RiskFormPage") },
  { path: "processus", element: lazyRoute(load.processList, "ProcessListPage") },
  { path: "processus/nouveau", element: lazyRoute(load.processForm, "ProcessFormPage") },
  { path: "processus/:id", element: lazyRoute(load.processForm, "ProcessFormPage") },
  { path: "directions", element: lazyRoute(load.directions, "DirectionsPage") },
  { path: "objets-auditables", element: lazyRoute(load.objects, "AuditableObjectsPage") },
];
