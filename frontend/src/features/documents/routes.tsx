import type { RouteObject } from "react-router-dom";
import { NumberingPage } from "./pages/NumberingPage";
import { TemplateDetailPage } from "./pages/TemplateDetailPage";
import { TemplatesPage } from "./pages/TemplatesPage";
import { DocumentDetailPage } from "./pages/DocumentDetailPage";
import { DocumentListPage } from "./pages/DocumentListPage";

/** Registre des documents (/documents) ; la garde de rôle est posée dans routes.tsx. */
export const documentRoutes: RouteObject[] = [
  { index: true, element: <DocumentListPage /> },
  { path: ":id", element: <DocumentDetailPage /> },
];

/** Gabarits et numérotation (/administration/documents), réservés à l'ADMIN par la garde parente. */
export const documentsAdminRoutes: RouteObject[] = [
  { index: true, element: <TemplatesPage /> },
  { path: "numerotation", element: <NumberingPage /> },
  { path: ":type", element: <TemplateDetailPage /> },
];
