import type { RouteObject } from "react-router-dom";
import { lazyRoute } from "@/components/lazyRoute";

const settings = () => import("./pages/SignatureSettingsPage");

/** Mode de signature (/administration/signatures) ; la garde ADMIN/RAI est posée dans routes.tsx. */
export const signatureAdminRoutes: RouteObject[] = [
  { index: true, element: lazyRoute(settings, "SignatureSettingsPage") },
];
