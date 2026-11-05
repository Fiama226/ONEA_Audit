import type { ReactNode } from "react";
import { Link, Outlet, createBrowserRouter, type RouteObject } from "react-router-dom";
import { RequireAccountManager } from "@/auth/RequireAccountManager";
import { RequireAuth } from "@/auth/RequireAuth";
import { RequireRole } from "@/auth/RequireRole";
import { EmptyState } from "@/components/EmptyState";
import { lazyRoute } from "@/components/lazyRoute";
import { documentRoutes, documentsAdminRoutes } from "@/features/documents/routes";
import { missionRoutes } from "@/features/missions/routes";
import { programmationRoutes } from "@/features/programmation/routes";
import { referentielRoutes } from "@/features/referentiel/routes";
import { signatureAdminRoutes } from "@/features/signatures/routes";
import { administrationRoutes } from "@/features/utilisateurs/routes";
import { fr } from "@/i18n/fr";
import { AppShell } from "@/layouts/AppShell";
import { rolesFor } from "@/layouts/navigation";
import { ErrorPage } from "@/pages/ErrorPage";

/**
 * Pages chargées à la demande pour alléger le JS d'entrée (budget D10) : les pages
 * d'authentification portent react-hook-form et zod, le tableau de bord ses graphiques.
 */
const authPages = {
  login: () => import("@/auth/LoginPage"),
  forgot: () => import("@/auth/ForgotPasswordPage"),
  reset: () => import("@/auth/ResetPasswordPage"),
  change: () => import("@/auth/ChangePasswordPage"),
};
const dashboard = () => import("@/features/dashboard/pages/DashboardPage");
const monCompte = () => import("@/features/tutoriel/pages/MonComptePage");

const governanceRules = () => import("@/features/gouvernance/pages/GovernanceRulesPage");
const auditJournal = () => import("@/features/gouvernance/pages/AuditJournalPage");

const rapportsList = () => import("@/features/communication/pages/RapportsDiffusesPage");
const rapportDetail = () => import("@/features/communication/pages/RapportDiffusePage");

/** Pages du lot 8 : suivi des recommandations, notifications, recherche. */
const suiviPages = {
  register: () => import("@/features/suivi/pages/RegisterPage"),
  action: () => import("@/features/suivi/pages/ActionPage"),
  extensions: () => import("@/features/suivi/pages/ExtensionRequestsPage"),
  reminders: () => import("@/features/suivi/pages/RemindersPage"),
  notifications: () => import("@/features/notifications/pages/NotificationsPage"),
  search: () => import("@/features/recherche/pages/SearchPage"),
};

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
  // Pages publiques : connexion et mot de passe oublié (chemins repris dans auth/paths.ts).
  { path: "/connexion", element: lazyRoute(authPages.login, "LoginPage") },
  {
    path: "/mot-de-passe-oublie",
    element: lazyRoute(authPages.forgot, "ForgotPasswordPage"),
  },
  {
    path: "/mot-de-passe/reinitialiser",
    element: lazyRoute(authPages.reset, "ResetPasswordPage"),
  },
  { path: "/erreur", element: <ErrorPage /> },
  {
    element: <RequireAuth />,
    children: [
      // Hors du shell : seule page accessible tant qu'un mot de passe temporaire n'est pas changé.
      {
        path: "/mot-de-passe/changer",
        element: lazyRoute(authPages.change, "ChangePasswordPage"),
      },
      {
        element: <AppShell />,
        children: [
          { path: "/", element: lazyRoute(dashboard, "DashboardPage") },
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
            element: guardedOutlet("/recommandations"),
            children: [
              { index: true, element: lazyRoute(suiviPages.register, "RegisterPage") },
              { path: "actions/:id", element: lazyRoute(suiviPages.action, "ActionPage") },
              {
                path: "reports",
                element: (
                  <RequireRole roles={["RAI"]}>
                    {lazyRoute(suiviPages.extensions, "ExtensionRequestsPage")}
                  </RequireRole>
                ),
              },
              {
                path: "relances",
                element: (
                  <RequireRole roles={["RAI"]}>
                    {lazyRoute(suiviPages.reminders, "RemindersPage")}
                  </RequireRole>
                ),
              },
            ],
          },
          {
            path: "/notifications",
            element: lazyRoute(suiviPages.notifications, "NotificationsPage"),
          },
          { path: "/mon-compte", element: lazyRoute(monCompte, "MonComptePage") },
          { path: "/recherche", element: lazyRoute(suiviPages.search, "SearchPage") },
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
            // Comptes : l'ADMIN et tout agent qui détient un droit délégué de gestion des comptes.
            path: "/administration",
            element: (
              <RequireAccountManager>
                <Outlet />
              </RequireAccountManager>
            ),
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
          // Règles de gouvernance : lecture ADMIN, RAI et DG ; écriture ADMIN (le serveur répond 403).
          {
            path: "/administration/gouvernance",
            element: guarded(
              "/administration/gouvernance",
              lazyRoute(governanceRules, "GovernanceRulesPage"),
            ),
          },
          {
            path: "/journal-audit",
            element: guarded("/journal-audit", lazyRoute(auditJournal, "AuditJournalPage")),
          },
          { path: "*", element: <NotFound /> },
        ],
      },
    ],
  },
];

export const createAppRouter = () => createBrowserRouter(appRoutes);
