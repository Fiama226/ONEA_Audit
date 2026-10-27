import type { ReactNode } from "react";
import { createBrowserRouter, type RouteObject } from "react-router-dom";
import { RequireAuth } from "@/auth/RequireAuth";
import { RequireRole } from "@/auth/RequireRole";
import { DashboardPage } from "@/features/dashboard/pages/DashboardPage";
import { fr } from "@/i18n/fr";
import { AppShell } from "@/layouts/AppShell";
import { rolesFor } from "@/layouts/navigation";
import { CallbackPage } from "@/pages/CallbackPage";
import { ErrorPage } from "@/pages/ErrorPage";
import { LoginPage } from "@/pages/LoginPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";

/** Applique la garde de rôle déclarée dans layouts/navigation.ts (source unique). */
function guarded(path: string, element: ReactNode): ReactNode {
  const roles = rolesFor(path);
  return roles ? <RequireRole roles={roles}>{element}</RequireRole> : element;
}

function NotFound() {
  return <p>{fr.errors.notFound}</p>;
}

export const appRoutes: RouteObject[] = [
  { path: "/connexion", element: <LoginPage /> },
  { path: "/callback", element: <CallbackPage /> },
  { path: "/erreur", element: <ErrorPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: "/", element: <DashboardPage /> },
          { path: "/missions", element: <PlaceholderPage title={fr.nav.missions} /> },
          {
            path: "/referentiel",
            element: guarded("/referentiel", <PlaceholderPage title={fr.nav.referentiel} />),
          },
          {
            path: "/recommandations",
            element: <PlaceholderPage title={fr.nav.recommandations} />,
          },
          { path: "/documents", element: <PlaceholderPage title={fr.nav.documents} /> },
          {
            path: "/administration",
            element: guarded("/administration", <PlaceholderPage title={fr.nav.administration} />),
          },
          { path: "*", element: <NotFound /> },
        ],
      },
    ],
  },
];

export const createAppRouter = () => createBrowserRouter(appRoutes);
