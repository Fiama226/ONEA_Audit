import type { RouteObject } from "react-router-dom";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { fr } from "@/i18n/fr";
import { NumberingPage } from "./pages/NumberingPage";
import { TemplateDetailPage } from "./pages/TemplateDetailPage";
import { TemplatesPage } from "./pages/TemplatesPage";

/** Registre des documents (/documents) ; les pages arrivent avec la tâche T12. */
export const documentRoutes: RouteObject[] = [
  { index: true, element: <PlaceholderPage title={fr.nav.documents} /> },
];

/** Gabarits et numérotation (/administration/documents), réservés à l'ADMIN par la garde parente. */
export const documentsAdminRoutes: RouteObject[] = [
  { index: true, element: <TemplatesPage /> },
  { path: "numerotation", element: <NumberingPage /> },
  { path: ":type", element: <TemplateDetailPage /> },
];
