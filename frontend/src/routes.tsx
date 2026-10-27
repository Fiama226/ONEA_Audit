import { createBrowserRouter, type RouteObject } from "react-router-dom";
import { RequireAuth } from "@/auth/RequireAuth";
import { RequireRole } from "@/auth/RequireRole";
import { DashboardPage } from "@/features/dashboard/pages/DashboardPage";
import { fr } from "@/i18n/fr";
import { AppShell } from "@/layouts/AppShell";
import { CallbackPage } from "@/pages/CallbackPage";
import { ErrorPage } from "@/pages/ErrorPage";
import { LoginPage } from "@/pages/LoginPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";

function NotFound() {
  return <p className="py-6">{fr.errors.notFound}</p>;
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
            element: (
              <RequireRole roles={["ADMIN", "RAI", "AUDITEUR"]}>
                <PlaceholderPage title={fr.nav.referentiel} />
              </RequireRole>
            ),
          },
          {
            path: "/recommandations",
            element: <PlaceholderPage title={fr.nav.recommandations} />,
          },
          { path: "/documents", element: <PlaceholderPage title={fr.nav.documents} /> },
          {
            path: "/administration",
            element: (
              <RequireRole roles={["ADMIN"]}>
                <PlaceholderPage title={fr.nav.administration} />
              </RequireRole>
            ),
          },
          { path: "*", element: <NotFound /> },
        ],
      },
    ],
  },
];

export const createAppRouter = () => createBrowserRouter(appRoutes);
