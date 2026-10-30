import type { ReactNode } from "react";
import { Link, Outlet, createBrowserRouter, type RouteObject } from "react-router-dom";
import { RequireAuth } from "@/auth/RequireAuth";
import { RequireRole } from "@/auth/RequireRole";
import { EmptyState } from "@/components/EmptyState";
import { lazyRoute } from "@/components/lazyRoute";
import { DashboardPage } from "@/features/dashboard/pages/DashboardPage";
import { documentRoutes, documentsAdminRoutes } from "@/features/documents/routes";
import { missionRoutes } from "@/features/missions/routes";
import { programmationRoutes } from "@/features/programmation/routes";
import { referentielRoutes } from "@/features/referentiel/routes";
import { signatureAdminRoutes } from "@/features/signatures/routes";
import { administrationRoutes } from "@/features/utilisateurs/routes";
import { fr } from "@/i18n/fr";
import { AppShell } from "@/layouts/AppShell";
import { rolesFor } from "@/layouts/navigation";
import { CallbackPage } from "@/pages/CallbackPage";
import { ErrorPage } from "@/pages/ErrorPage";
import { LoginPage } from "@/pages/LoginPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";

const rapportsList = () => import("@/features/communication/pages/RapportsDiffusesPage");
const rapportDetail = () => import("@/features/communication/pages/RapportDiffusePage");

/** Applique la garde de rôle déclarée dans layouts/navigation.ts (source unique). */
function guarded(path: string, element: ReactNode): ReactNode {
  const roles = rolesFor(path);
  return roles ? <RequireRole roles={roles}>{element}</RequireRole> : element;
}

/** Garde de rôle pour un groupe de routes enfants. */
function guardedOutlet(path: string): ReactNode {
  return guarded(path, <Outlet />);
}

function NotFound() {
  return (
    <>
      <EmptyState
        title={fr.errors.pageNotFoundTitle}
        description={fr.errors.pageNotFound}
        illustration={false}
      />
      <Link
        to="/"
        className="mt-4 inline-block text-sm font-medium text-primary underline-offset-[3px] hover:underline"
      >
        {fr.errors.backToDashboard}
      </Link>
    </>
  );
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
          { path: "/missions", children: missionRoutes, element: guardedOutlet("/missions") },
          {
            path: "/programme-annuel",
            element: guarded("/programme-annuel", <Outlet />),
            children: programmationRoutes,
          },
          {
            path: "/referentiel",
            element: guarded(
              "/referentiel",
              lazyRoute(
                () => import("@/features/referentiel/components/ReferentielLayout"),
                "ReferentielLayout",
              ),
            ),
            children: referentielRoutes,
          },
          {
            path: "/recommandations",
            element: <PlaceholderPage title={fr.nav.recommandations} />,
          },
          {
            path: "/rapports",
            element: guardedOutlet("/rapports"),
            children: [
              { index: true, element: lazyRoute(rapportsList, "RapportsDiffusesPage") },
              { path: ":id", element: lazyRoute(rapportDetail, "RapportDiffusePage") },
            ],
          },
          { path: "/documents", children: documentRoutes, element: guardedOutlet("/documents") },
          {
            path: "/administration",
            element: guarded("/administration", <Outlet />),
            children: administrationRoutes,
          },
          // Gabarits et numérotation : lecture ADMIN et RAI (garde propre, hors de la garde ADMIN du parent).
          {
            path: "/administration/documents",
            children: documentsAdminRoutes,
            element: guardedOutlet("/administration/documents"),
          },
          // Mode de signature : lecture ADMIN et RAI ; l'écriture reste ADMIN (le serveur répond 403).
          {
            path: "/administration/signatures",
            children: signatureAdminRoutes,
            element: guardedOutlet("/administration/signatures"),
          },
          { path: "*", element: <NotFound /> },
        ],
      },
    ],
  },
];

export const createAppRouter = () => createBrowserRouter(appRoutes);
