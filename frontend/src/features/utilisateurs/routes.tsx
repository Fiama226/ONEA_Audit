import { Navigate, type RouteObject } from "react-router-dom";
import { UserDetailPage } from "./pages/UserDetailPage";
import { UserListPage } from "./pages/UserListPage";

/** Routes enfants de `/administration` (la garde ADMIN est posée dans routes.tsx). */
export const administrationRoutes: RouteObject[] = [
  { index: true, element: <Navigate to="utilisateurs" replace /> },
  { path: "utilisateurs", element: <UserListPage /> },
  { path: "utilisateurs/:id", element: <UserDetailPage /> },
];
