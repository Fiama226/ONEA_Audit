import type { RouteObject } from "react-router-dom";
import { DocumentDetailPage } from "./pages/DocumentDetailPage";
import { DocumentListPage } from "./pages/DocumentListPage";

/** Registre des documents (/documents) ; la garde de rôle est posée dans routes.tsx. */
export const documentRoutes: RouteObject[] = [
  { index: true, element: <DocumentListPage /> },
  { path: ":id", element: <DocumentDetailPage /> },
];

/** Gabarits et numérotation (/administration/documents) ; les pages arrivent avec la tâche T9. */
export const documentsAdminRoutes: RouteObject[] = [];
