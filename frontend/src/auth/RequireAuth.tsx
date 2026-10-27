import { Navigate, Outlet, useLocation } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { ErrorPage } from "@/pages/ErrorPage";
import { useAuth } from "./useAuth";

export function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <p role="status" className="p-6 text-muted-foreground">
        {fr.common.loading}
      </p>
    );
  }
  if (status === "error") return <ErrorPage />;
  if (status === "anonymous") {
    const from = `${location.pathname}${location.search}`;
    return <Navigate to="/connexion" replace state={{ from }} />;
  }
  return <Outlet />;
}
