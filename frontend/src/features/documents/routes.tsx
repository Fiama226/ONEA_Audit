import type { RouteObject } from "react-router-dom";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { fr } from "@/i18n/fr";
import { lazyRoute } from "@/components/lazyRoute";

const templates = () => import("./pages/TemplatesPage");
const numbering = () => import("./pages/NumberingPage");
const templateDetail = () => import("./pages/TemplateDetailPage");

/** Registre des documents (/documents) ; les pages arrivent avec la tâche T12. */
export const documentRoutes: RouteObject[] = [
  { index: true, element: <PlaceholderPage title={fr.nav.documents} /> },
];

/** Gabarits et numérotation (/administration/documents), réservés à l'ADMIN par la garde parente. */
export const documentsAdminRoutes: RouteObject[] = [
  { index: true, element: lazyRoute(templates, "TemplatesPage") },
  { path: "numerotation", element: lazyRoute(numbering, "NumberingPage") },
  { path: ":type", element: lazyRoute(templateDetail, "TemplateDetailPage") },
];
