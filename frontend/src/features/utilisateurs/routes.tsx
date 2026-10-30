import { Navigate, type RouteObject } from "react-router-dom";
import { lazyRoute } from "@/components/lazyRoute";

const list = () => import("./pages/UserListPage");
const detail = () => import("./pages/UserDetailPage");

/** Routes enfants de `/administration` (la garde ADMIN est posée dans routes.tsx). */
export const administrationRoutes: RouteObject[] = [
  { index: true, element: <Navigate to="utilisateurs" replace /> },
  { path: "utilisateurs", element: lazyRoute(list, "UserListPage") },
  { path: "utilisateurs/:id", element: lazyRoute(detail, "UserDetailPage") },
];
