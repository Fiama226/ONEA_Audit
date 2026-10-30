import type { RouteObject } from "react-router-dom";
import { lazyRoute } from "@/components/lazyRoute";

const templates = () => import("./pages/TemplatesPage");
const numbering = () => import("./pages/NumberingPage");
const templateDetail = () => import("./pages/TemplateDetailPage");
const documentList = () => import("./pages/DocumentListPage");
const documentDetail = () => import("./pages/DocumentDetailPage");

/** Registre des documents (/documents) ; la garde de rôle est posée dans routes.tsx. */
export const documentRoutes: RouteObject[] = [
  { index: true, element: lazyRoute(documentList, "DocumentListPage") },
  { path: ":id", element: lazyRoute(documentDetail, "DocumentDetailPage") },
];

/** Gabarits et numérotation (/administration/documents), réservés à l'ADMIN par la garde parente. */
export const documentsAdminRoutes: RouteObject[] = [
  { index: true, element: lazyRoute(templates, "TemplatesPage") },
  { path: "numerotation", element: lazyRoute(numbering, "NumberingPage") },
  { path: ":type", element: lazyRoute(templateDetail, "TemplateDetailPage") },
];
