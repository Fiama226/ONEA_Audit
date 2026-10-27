import { createBrowserRouter, type RouteObject } from "react-router-dom";
import { App } from "@/App";
import { RequireAuth } from "@/auth/RequireAuth";
import { fr } from "@/i18n/fr";
import { CallbackPage } from "@/pages/CallbackPage";
import { ErrorPage } from "@/pages/ErrorPage";
import { LoginPage } from "@/pages/LoginPage";

function NotFound() {
  return <p className="p-6">{fr.errors.notFound}</p>;
}

export const appRoutes: RouteObject[] = [
  { path: "/connexion", element: <LoginPage /> },
  { path: "/callback", element: <CallbackPage /> },
  { path: "/erreur", element: <ErrorPage /> },
  {
    element: <RequireAuth />,
    children: [
      { path: "/", element: <App /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export const createAppRouter = () => createBrowserRouter(appRoutes);
