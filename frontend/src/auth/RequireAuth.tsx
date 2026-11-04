import { Navigate, Outlet, useLocation } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { ErrorPage } from "@/pages/ErrorPage";
import { AUTH_PATHS } from "./paths";
import { useAuth } from "./useAuth";

export function RequireAuth() {
  const { status, etape, loggedOut } = useAuth();
  const location = useLocation();
  const from = `${location.pathname}${location.search}${location.hash}`;

  if (status === "loading") {
    return (
      <p role="status" className="p-6 text-muted-foreground">
        {fr.common.loading}
      </p>
    );
  }
  if (status === "error") return <ErrorPage />;
  if (status === "anonymous") {
    // Après une déconnexion volontaire, l'utilisateur suivant ne reçoit pas l'adresse quittée.
    return <Navigate to={AUTH_PATHS.login} replace state={loggedOut ? undefined : { from }} />;
  }
  // Mot de passe temporaire : rien d'autre n'est accessible avant le changement.
  if (etape === "CHANGER_MOT_DE_PASSE" && location.pathname !== AUTH_PATHS.change) {
    return <Navigate to={AUTH_PATHS.change} replace state={{ from }} />;
  }
  return <Outlet />;
}
