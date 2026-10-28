import type { RouteObject } from "react-router-dom";
import { AuditPlanDetailPage } from "./pages/AuditPlanDetailPage";
import { AuditPlanLineFormPage } from "./pages/AuditPlanLineFormPage";
import { AuditPlanListPage } from "./pages/AuditPlanListPage";

/** Routes enfants de `/programme-annuel` (la garde de rôle est posée dans routes.tsx). */
export const programmationRoutes: RouteObject[] = [
  { index: true, element: <AuditPlanListPage /> },
  { path: ":id", element: <AuditPlanDetailPage /> },
  { path: ":id/nouvelle-ligne", element: <AuditPlanLineFormPage creating /> },
  { path: "lignes/:lineId", element: <AuditPlanLineFormPage /> },
];
