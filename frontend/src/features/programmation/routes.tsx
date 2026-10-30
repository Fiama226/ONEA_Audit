import type { RouteObject } from "react-router-dom";
import { lazyRoute } from "@/components/lazyRoute";

const list = () => import("./pages/AuditPlanListPage");
const detail = () => import("./pages/AuditPlanDetailPage");
const lineForm = () => import("./pages/AuditPlanLineFormPage");

/** Routes enfants de `/programme-annuel` (la garde de rôle est posée dans routes.tsx). */
export const programmationRoutes: RouteObject[] = [
  { index: true, element: lazyRoute(list, "AuditPlanListPage") },
  { path: ":id", element: lazyRoute(detail, "AuditPlanDetailPage") },
  {
    path: ":id/nouvelle-ligne",
    element: lazyRoute(lineForm, "AuditPlanLineFormPage", { creating: true }),
  },
  { path: "lignes/:lineId", element: lazyRoute(lineForm, "AuditPlanLineFormPage") },
];
