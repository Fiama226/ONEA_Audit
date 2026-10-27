import { render } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { vi } from "vitest";
import { AuthProvider } from "@/auth/AuthProvider";
import type { OidcClient, OidcUser } from "@/auth/oidc";
import type { Me } from "@/auth/types";
import { appRoutes } from "@/routes";
import { API_URL, server } from "./msw";

export const TEST_TOKEN = "tok-123";

export function fakeUser(overrides: Partial<OidcUser> = {}): OidcUser {
  return { access_token: TEST_TOKEN, expired: false, state: undefined, ...overrides };
}

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
    ...overrides,
  };
}

export function mockOidc(user: OidcUser | null = null): OidcClient {
  return {
    getUser: vi.fn().mockResolvedValue(user),
    signinRedirect: vi.fn().mockResolvedValue(undefined),
    signinRedirectCallback: vi.fn().mockResolvedValue(user ?? fakeUser()),
    signoutRedirect: vi.fn().mockResolvedValue(undefined),
    removeUser: vi.fn().mockResolvedValue(undefined),
    events: {
      addUserLoaded: vi.fn(),
      removeUserLoaded: vi.fn(),
      addAccessTokenExpired: vi.fn(),
      removeAccessTokenExpired: vi.fn(),
      addSilentRenewError: vi.fn(),
      removeSilentRenewError: vi.fn(),
    },
  };
}

/** Récupère le dernier callback enregistré via la méthode d'événement `name`. */
export function capturedHandler<A extends unknown[]>(
  fn: unknown,
): (...args: A) => void {
  const calls = (fn as { mock: { calls: unknown[][] } }).mock.calls;
  const cb = calls[calls.length - 1]?.[0];
  if (typeof cb !== "function") throw new Error("aucun callback enregistré");
  return cb as (...args: A) => void;
}

/** Sert /me uniquement si la requête porte `Authorization: Bearer <token>`, sinon 401. */
export function serveMe(body: object = fakeMe(), token: string = TEST_TOKEN) {
  server.use(
    http.get(`${API_URL}/api/v1/me/`, ({ request }) => {
      if (request.headers.get("Authorization") !== `Bearer ${token}`) {
        return HttpResponse.json({}, { status: 401 });
      }
      return HttpResponse.json(body);
    }),
  );
}

export function renderApp(path: string | { pathname: string; state?: unknown }, oidc: OidcClient) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  render(
    <AuthProvider userManager={oidc}>
      <RouterProvider router={router} />
    </AuthProvider>,
  );
  return router;
}
