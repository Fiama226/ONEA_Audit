import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { AuthProvider } from "@/auth/AuthProvider";
import type { Etape, Me } from "@/auth/types";
import { appRoutes } from "@/routes";
import { API_URL, server } from "./msw";

export const AUTH_URL = `${API_URL}/api/v1/auth`;

export function fakeMe(overrides: Partial<Record<keyof Me, unknown>> = {}) {
  return {
    id: 1,
    username: "rai",
    email: "rai@onea.bf",
    first_name: "Awa",
    last_name: "Ouedraogo",
    role: "RAI",
    direction_code: "DAI",
    fonction: "Responsable audit interne",
    tutoriel: { version_vue: 1, termine_le: null },
    otp_connexion_actif: false,
    gestion_comptes: { creer: false, reinitialiser: false, roles: false, desactiver: false },
    ...overrides,
  };
}

/** Sert GET /api/v1/auth/session/ : session ouverte avec `me` et l'étape donnée. */
export function serveSession(me: object = fakeMe(), etape: Etape = "OK") {
  server.use(http.get(`${AUTH_URL}/session/`, () => HttpResponse.json({ etape, me })));
}

/** Corps 401 du serveur (session absente ou expirée). */
export function unauthorized(detail = "Informations d'authentification non fournies.") {
  return HttpResponse.json({ detail, errors: {} }, { status: 401 });
}

/** Rend l'application complète (routes réelles) avec le vrai AuthProvider. */
export function renderApp(path: string | { pathname: string; state?: unknown }) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return { router, client };
}
