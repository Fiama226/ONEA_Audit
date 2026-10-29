import type { RouteObject } from "react-router-dom";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { fr } from "@/i18n/fr";

/** Registre des documents (/documents) ; les pages arrivent avec la tâche T12. */
export const documentRoutes: RouteObject[] = [
  { index: true, element: <PlaceholderPage title={fr.nav.documents} /> },
];

/** Gabarits et numérotation (/administration/documents) ; les pages arrivent avec la tâche T9/T10. */
export const documentsAdminRoutes: RouteObject[] = [];
